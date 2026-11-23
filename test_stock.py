import unittest
from stock import Api, ApiError, quantity, errors

class Tests(unittest.TestCase):
    def test_quantity(self):
        self.assertEqual(quantity('2,5'),2.5)
        for v in ['nan','inf','-1','abc']:
            with self.assertRaises(ApiError):quantity(v)
    def test_nested_partial_error(self):
        with self.assertRaises(ApiError):errors({'results':[{'faultCode':9,'faultString':'blocked'}]})
    def test_exact_external_only(self):
        a=Api('test'); a.call=lambda *args,**kw:{'results':[{'productId':1,'productStocksData':{'productStocksQuantities':[{'stockId':1,'productSizesData':[{'sizeId':'uniw','productSizeCodeExternal':'001','productSizeQuantity':3}]}]}}]}
        self.assertEqual(a.lookup('001')[0]['quantity'],3)
        with self.assertRaises(ApiError):a.lookup('1')
    def test_changed_stock_blocks_write(self):
        a=Api('test'); row={'code':'test','stock':1,'quantity':3}
        a.lookup=lambda code:[dict(row,quantity=4)]
        a.call=lambda *args,**kw:self.fail('write must not happen')
        with self.assertRaises(ApiError):a.update(row,5)
    def test_readback_mismatch(self):
        a=Api('test'); row={'code':'test','stock':1,'quantity':3}
        a.lookup=lambda code:[dict(row)]
        calls=[]; a.call=lambda *args,**kw:calls.append(args)
        with self.assertRaises(ApiError):a.update(row,5)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][2]['params']['products'][0]['productSizeQuantity'],5)
if __name__=='__main__':unittest.main()
