
class TokenRange:
    def __init__(self, l, t, r, b):
        self.l = l
        self.t = t
        self.r = r
        self.b = b

    def __str__(self):
        return "{}, {}, {}, {}".format(self.l, self.t, self.r, self.b)

    def contains(self, pos_list):
        if len(pos_list) != 4:
            return False
        l, t, r, b = pos_list[0], pos_list[1], pos_list[2], pos_list[3]
        return l >= self.l and t >= self.t and r <= self.r and b <= self.b
    
    def intersect(self, range2):
        if self.l > range2.r:
            return False
        if self.t > range2.b:
            return False
        if self.b < range2.t:
            return False
        if self.r < range2.l:
            return False
        return True

class InvoiceLayout:
    supported_layouts = [
        {
            "keyword": "社会信用代码",
            "layout": {
        "title": { "range": TokenRange(20, 0, 80, 20), "fields": []},
        "header": { "range": TokenRange(70, 0, 100, 20), "fields": ["发票号码", "发票日期"]},
        "buyer": { "range": TokenRange(1, 20, 50, 45), "fields": ["名称", "社会信用代码"]},
        "seller": { "range": TokenRange(51, 20, 100, 45), "fields": ["名称", "社会信用代码"]},
        "details": { "range": TokenRange(0, 43, 100, 90), "fields": []},
        "summary": { "range": TokenRange(1, 90, 100, 100), "fields": ["小写"]},
            }
        },
        {
            "keyword": "开户行及账号",
            "layout": {
        "title": { "range": TokenRange(20, 0, 73, 20), "fields": []},
        "header": { "range": TokenRange(70, 0, 100, 20), "fields": ["发票代码", "发票号码", "开票日期"]},
        "buyer": { "range": TokenRange(2, 20, 60, 40), "fields": ["称","纳税人识别号","地址","开户行及账号"]},
        "seller": { "range": TokenRange(2, 80, 60, 100), "fields": ["称","纳税人识别号","地址","开户行及账号"]},
        "details": { "range": TokenRange(0, 38, 100, 77), "fields": []},
        "summary": { "range": TokenRange(1, 76, 100, 84), "fields": ["小写"]},
            }
        }
    ]

    @staticmethod
    def getLayout(tokens):
        for i in range(len(InvoiceLayout.supported_layouts)):
            l = InvoiceLayout.supported_layouts[i]
            for tok in tokens:
                if l['keyword'] in tok['transcription']:
                    return InvoiceLayout(i)
        return None
    
    def __init__(self, layout_id):
        self.layout = None
        if layout_id in range(len(InvoiceLayout.supported_layouts)):
            self.layout = InvoiceLayout.supported_layouts[layout_id]['layout']

    def getTitleFields(self):
        return self.layout["title"]["fields"]

    def getTitleRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["title"]["range"])

    def getHeaderFields(self):
        return self.layout["header"]["fields"]

    def getHeaderRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["header"]["range"])

    def getBuyerFields(self):
        return self.layout["buyer"]["fields"]

    def getBuyerRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["buyer"]["range"])

    def getSellerFields(self):
        return self.layout["seller"]["fields"]

    def getSellerRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["seller"]["range"])

    def getSummaryFields(self):
        return self.layout["summary"]["fields"]

    def getSummaryRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["summary"]["range"])

    def getDetailsFields(self):
        return self.layout["details"]["fields"]

    def getDetailsRange(self, invoiceRange):
        return InvoiceLayout.getRange(invoiceRange, self.layout["details"]["range"])

    def getRange(invoiceRange, rng):
        if not rng:
            return TokenRange()
        l = invoiceRange.l + int((invoiceRange.r - invoiceRange.l) * rng.l / 100)
        r = invoiceRange.l + int((invoiceRange.r - invoiceRange.l) * rng.r / 100)
        t = invoiceRange.t + int((invoiceRange.b - invoiceRange.t) * rng.t / 100)
        b = invoiceRange.t + int((invoiceRange.b - invoiceRange.t) * rng.b / 100)
        return TokenRange(l, t, r, b)

def getInvoiceRange(result):
    l, t, r, b = -1, -1, -1, -1
    for tok in result:
        if tok['bbox'][0] < l or l == -1:
            l = tok['bbox'][0]
        if tok['bbox'][1] < t or t == -1:
            if "发票" in tok['transcription']:
                t = tok['bbox'][1] - 20
                if t < 0:
                    t = 0
        if tok['bbox'][2] > r or r == -1:
            r = tok['bbox'][2]
        if tok['bbox'][3] > b or b == -1:
            if "价税合计" in tok['transcription']:
                b = tok['bbox'][3] + 20
            if "开户行及账号" in tok['transcription']:
                b = tok['bbox'][3] + 20
    return TokenRange(l, t, r, b)

class InvoiceTitle:
    SupportedTypes = {
        0: "未识别发票",
        1: "电子发票（普通发票）",
        2: "电子发票（增值税专用发票）"
    }

    def __init__(self, tokens, r, f, logger):
        self.range = r
        self.logger = logger
        self.tokens = []
        self.invoice_type = 0
        for tok in tokens:
            if self.range.contains(tok['bbox']):
                self.tokens.append(tok['transcription'])
    
    def getType(self):
        if self.invoice_type == 0:
            self.parse()
        return self.SupportedTypes[self.invoice_type]

    def parse(self):
        self.logger.info("title tokens: {}".format(self.tokens))
        for tok in self.tokens:
            if "值税" in tok:
                self.invoice_type = 2
                return
            elif "普通" in tok:
                self.invoice_type = 1
                return

    def __str__(self):
        return "{}".format(self.getType())

class InvoiceSegment:
    def __init__(self, segname, tokens, r, fields, logger):
        self.segname = segname
        self.range = r
        self.logger = logger
        self.requied_fields = fields
        self.tokens = []
        self.values = {}
        for tok in tokens:
            if self.range.contains(tok['bbox']):
                self.tokens.append(tok['transcription'])

    def getRequiredFields(self):
        return self.requied_fields

    def parse(self):
        for f in self.getRequiredFields():
            for tok in self.tokens:
                if f in tok:
                    self.values[f] = tok
    
    def __str__(self):
        return "{}".format(self.values)

class InvoiceHeader(InvoiceSegment):
    def __init__(self, tokens, r, f, logger):
        return super().__init__("header", tokens, r, f, logger)

class InvoiceBuyerInfo(InvoiceSegment):
    def __init__(self, tokens, r, f, logger):
        return super().__init__("buyer", tokens, r, f, logger)

class InvoiceSellerInfo(InvoiceSegment):
    def __init__(self, tokens, r, f, logger):
        return super().__init__("seller", tokens, r, f, logger)

class InvoiceSummaryInfo(InvoiceSegment):
    def __init__(self, tokens, r, f, logger):
        return super().__init__("summary", tokens, r, f, logger)

class InvoiceDetails(InvoiceSegment):
    def __init__(self, tokens, r, f, logger):
        super().__init__("details", tokens, r, f, logger)
        self.tokens = []
        self.columns = []
        self.column_tokens = []
        self.value_tokens = []
        for tok in tokens:
            if self.range.contains(tok['bbox']):
                self.tokens.append((tok['transcription'], tok['bbox']))

    def parse(self):
        if len(self.tokens) == 0:
            return
        # 1. get columns
        head_row = self.tokens[0][1][1]
        for tok in self.tokens:
            if tok[1][1] < head_row:
                head_row = tok[1][1]
        for tok in self.tokens:
            if tok[1][1] < head_row + 10:
                self.column_tokens.append(tok)
            else:
                self.value_tokens.append(tok)
        for tok in self.column_tokens:
            self.columns.append({
                "name": tok[0],
                "left": tok[1][0],
                "right": tok[1][2]
            })
        # 2. validate columns
        if not self.validate_columns():
            return
        # 3. add rows
        row_tops = self.get_row_ranges()
        for i in range(len(row_tops) - 1):
            row_v = {}
            for col in self.columns:
                l, t, r, b = col["left"], row_tops[i], col["right"], row_tops[i+1]
                item_range = TokenRange(l, t, r, b)
                for tok in self.value_tokens:
                    if item_range.intersect(TokenRange(tok[1][0], tok[1][1], tok[1][2], tok[1][3])):
                        row_v[col["name"]] = tok[0]
            self.values[i] = row_v

    def validate_columns(self):
        required_column = "税额"
        for col in self.columns:
            if required_column in col["name"]:
                return True
        self.columns.sort(key=lambda col: col['left'])
        if self.columns[-2]['name'] + self.columns[-1]['name'] == required_column:
            self.columns[-2]['name'] = required_column
            self.columns[-2]['right'] = max(self.columns[-2]['right'], self.columns[-1]['right'])
            self.columns.pop()
            return True

        return False

    def get_row_ranges(self):
        width_ranges = (0, 0)
        required_column = "税额"
        for col in self.columns:
            if required_column in col["name"]:
                width_ranges = (col["left"], col["right"])
                break

        row_tops = []
        row_bottom = 0
        for tok in self.value_tokens:
            if tok[1][0] < width_ranges[1] and tok[1][2] > width_ranges[0]:
                row_tops.append(tok[1][1])
                if tok[1][3] > row_bottom:
                    row_bottom = tok[1][3]
        row_tops.append(row_bottom)
        row_tops.sort()
        return row_tops

class Invoice:
    def __init__(self, tokens, logger):
        self.tokens = tokens
        self.logger = logger
        self.layout = None
        self.title = None
        self.header = None
        self.buyer = None
        self.seller = None
        self.details = None
        self.summary = None
    
    def parse(self):
        token_ranges = getInvoiceRange(self.tokens)
        self.logger.info("token ranges: {}".format(token_ranges))
        self.layout = InvoiceLayout.getLayout(self.tokens)
        if self.layout is None:
            return
        self.title = InvoiceTitle(self.tokens, self.layout.getTitleRange(token_ranges), self.layout.getTitleFields(), self.logger)
        self.title.parse()
        self.header = InvoiceHeader(self.tokens, self.layout.getHeaderRange(token_ranges), self.layout.getHeaderFields(), self.logger)
        self.header.parse()
        self.buyer = InvoiceBuyerInfo(self.tokens, self.layout.getBuyerRange(token_ranges), self.layout.getBuyerFields(), self.logger)
        self.buyer.parse()
        self.seller = InvoiceSellerInfo(self.tokens, self.layout.getSellerRange(token_ranges), self.layout.getSellerFields(), self.logger)
        self.seller.parse()
        self.summary = InvoiceSummaryInfo(self.tokens, self.layout.getSummaryRange(token_ranges), self.layout.getSummaryFields(), self.logger)
        self.summary.parse()
        self.details = InvoiceDetails(self.tokens, self.layout.getDetailsRange(token_ranges), self.layout.getDetailsFields(), self.logger)
        self.details.parse()

    def get_parse_result(self):
        x = {
            "title": "{}".format(self.title),
            "header": "{}".format(self.header),
            "buyer": "{}".format(self.buyer),
            "seller": "{}".format(self.seller),
            "summary": "{}".format(self.summary),
            "details": "{}".format(self.details)
        }
        return x

    def __str__(self):
        return "{}".format(self.get_parse_result())

if __name__ == "__main__":
    pass
