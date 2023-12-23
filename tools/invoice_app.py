
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import os
import sys
import time

__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, '..')))

os.environ["FLAGS_allocator_strategy"] = 'auto_growth'
import json
import paddle

from ppocr.data import create_operators, transform
from ppocr.modeling.architectures import build_model
from ppocr.postprocess import build_post_process
from ppocr.utils.save_load import load_model
from ppocr.utils.visual import draw_ser_results
from ppocr.utils.utility import get_image_file_list, load_vqa_bio_label_maps
import tools.program as program
from invoice import Invoice


def to_tensor(data):
    import numbers
    from collections import defaultdict
    data_dict = defaultdict(list)
    to_tensor_idxs = []

    for idx, v in enumerate(data):
        if isinstance(v, (np.ndarray, paddle.Tensor, numbers.Number)):
            if idx not in to_tensor_idxs:
                to_tensor_idxs.append(idx)
        data_dict[idx].append(v)
    for idx in to_tensor_idxs:
        data_dict[idx] = paddle.to_tensor(data_dict[idx])
    return list(data_dict.values())


class SerPredictor(object):
    def __init__(self, config):
        global_config = config['Global']
        self.algorithm = config['Architecture']["algorithm"]

        # build post process
        self.post_process_class = build_post_process(config['PostProcess'],
                                                     global_config)

        # build model
        self.model = build_model(config['Architecture'])

        load_model(
            config, self.model, model_type=config['Architecture']["model_type"])

        from paddleocr import PaddleOCR

        self.ocr_engine = PaddleOCR(
            use_angle_cls=False,
            show_log=False,
            rec_model_dir=global_config.get("kie_rec_model_dir", None),
            det_model_dir=global_config.get("kie_det_model_dir", None),
            use_gpu=global_config['use_gpu'])

        # create data ops
        transforms = []
        for op in config['Eval']['dataset']['transforms']:
            op_name = list(op)[0]
            if 'Label' in op_name:
                op[op_name]['ocr_engine'] = self.ocr_engine
            elif op_name == 'KeepKeys':
                op[op_name]['keep_keys'] = [
                    'input_ids', 'bbox', 'attention_mask', 'token_type_ids',
                    'image', 'labels', 'segment_offset_id', 'ocr_info',
                    'entities'
                ]

            transforms.append(op)
        if config["Global"].get("infer_mode", None) is None:
            global_config['infer_mode'] = True
        self.ops = create_operators(config['Eval']['dataset']['transforms'],
                                    global_config)
        self.model.eval()

    def __call__(self, data):
        with open(data["img_path"], 'rb') as f:
            img = f.read()
        data["image"] = img
        batch = transform(data, self.ops)
        batch = to_tensor(batch)
        preds = self.model(batch)

        post_result = self.post_process_class(
            preds, segment_offset_ids=batch[6], ocr_infos=batch[7])
        return post_result, batch

if __name__ == '__main__':
    config, device, logger, vdl_writer = program.preprocess()
    # os.makedirs(config['Global']['save_res_path'], exist_ok=True)

    ser_engine = SerPredictor(config)

    infer_imgs = get_image_file_list(config['Global']['infer_img'])
    for idx, info in enumerate(infer_imgs):
        if config["Global"].get("infer_mode", None) is False:
            data_line = info.decode('utf-8')
            substr = data_line.strip("\n").split("\t")
            img_path = os.path.join(data_dir, substr[0])
            data = {'img_path': img_path, 'label': substr[1]}
        else:
            img_path = info
            data = {'img_path': img_path}

        if os.path.basename(img_path)[-3:] == 'pdf':
            import fitz
            new_img_path = img_path + '.png'
            if not os.path.exists(new_img_path):
                doc = fitz.open(img_path)
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                pix.save(new_img_path)
            data['img_path'] = new_img_path
        elif os.path.basename(img_path)[-3:] == 'ofd':
            from PIL import Image
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfbase import pdfmetrics
            from easyofd.ofd import OFD
            pdfmetrics.registerFont(TTFont('宋体', './doc/invoice/AR-PL-SungtiL-GB.ttf'))
            pdfmetrics.registerFont(TTFont('楷体', './doc/invoice/AR-PL-KaitiM-GB.ttf'))

            new_img_path = img_path + '.jpg'
            if not os.path.exists(new_img_path):
                ofd = OFD()
                ofd.read(img_path, 'path')
                images = ofd.to_jpg()
                Image.fromarray(images[0]).save(new_img_path)
            data['img_path'] = new_img_path

        result, _ = ser_engine(data)
        result = result[0]
        # logger.info("{}".format(result))

        invoice = Invoice(result, logger)
        invoice.parse()
        logger.info("{}".format(invoice))
