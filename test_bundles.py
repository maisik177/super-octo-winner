import unittest
from stock import Api, ApiError

class BundleTests(unittest.TestCase):
    def test_all_batches_including_hidden(self):
        a=Api('test');a.product_by_external=lambda code:{'productId':7,'bundledIds':list(range(1,102))}
        calls=[]
        def call(endpoint,params):
            ids=list(map(int,params['productIds'].split(',')));calls.append(ids)
            return {'results':[{'productId':i,'productType':'product_bundle','productIsVisible':'n','productRetailPrice':10} for i in ids]}
        a.call=call
        self.assertEqual(len(a.bundles('001')),101)
        self.assertEqual(list(map(len,calls)),[100,1])
    def test_partial_response_rejected(self):
        a=Api('test');a.product_by_external=lambda code:{'productId':7,'bundledIds':[1,2]}
        a.call=lambda *args,**kwargs:{'results':[{'productId':1}]}
        with self.assertRaises(ApiError):a.bundles('001')
    def test_price_write_and_readback(self):
        a=Api('test');a.product_by_external=lambda code:{'productId':7,'bundledIds':[8]}
        product={'productId':8,'productType':'product_bundle','productRetailPrice':12}
        row=a.bundle_row(product,'001',7);calls=[]
        product['productRetailPrice']='12.00'
        product['productDescriptionsLangData']=[{'langId':'pol','productName':'Nowa nazwa'}]
        def call(endpoint,method='GET',body=None,params=None):
            if method=='PUT':
                calls.append(body)
                product['productRetailPrice']=body['params']['products'][0]['productRetailPrice']
                return {'results':[{'faultCode':0}]}
            return {'results':[{'productId':80},dict(product)]}
        a.call=call
        after=a.update_bundle_price(row,'17,45')
        self.assertEqual(after['price'],17.45)
        self.assertEqual(calls,[{'params':{'products':[{'productId':8,'priceChangeMode':'amount_set','productRetailPrice':17.45}]}}])
    def test_changed_price_blocks_write(self):
        a=Api('test')
        a.product_by_external=lambda code:{'productId':7,'bundledIds':['8']}
        product={'productId':8,'productType':'product_bundle','productRetailPrice':12}
        row=a.bundle_row(product,'001',7)
        product['productRetailPrice']=13
        a.call=lambda endpoint,params:{'results':[product]}
        with self.assertRaisesRegex(ApiError,'z 12 na 13'):
            a.update_bundle_price(row,'17,45')

    def test_removed_membership_blocks_write(self):
        a=Api('test');a.product_by_external=lambda code:{'productId':7,'bundledIds':[]}
        a.call=lambda *args,**kw:self.fail('No write allowed')
        with self.assertRaises(ApiError):a.update_bundle_price({'source_code':'001','source_id':7,'product_id':8},12)
    def test_invalid_price_never_calls_api(self):
        a=Api('test');a.product_by_external=lambda code:self.fail('No API call expected')
        for price in ['NaN','-1','1.001','Infinity','abc']:
            with self.assertRaises(ApiError):a.update_bundle_price({},price)
if __name__=='__main__':unittest.main()

class UnitPriceTests(unittest.TestCase):
    def test_piece_counts(self):
        for count,price in [(50,81),(200,324),(2400,3888)]:
            row=Api.bundle_row({'productId':1,'productRetailPrice':price,'productBundleItems':[{'bundleQuantity':count}]},'test',2)
            self.assertEqual(row['pieces'],str(count))
            self.assertEqual(row['unit_price'],'1.6200')
    def test_missing_zero_and_mixed(self):
        for items in [[],[{'bundleQuantity':0}],[{}]]:
            row=Api.bundle_row({'productId':1,'productRetailPrice':10,'productBundleItems':items},'test',2)
            self.assertIsNone(row['unit_price'])
        row=Api.bundle_row({'productId':1,'productRetailPrice':10,'productBundleItems':[{'bundleQuantity':2},{'bundleQuantity':1}]},'test',2)
        self.assertEqual(row['pieces'],'3')
        self.assertEqual(row['unit_price'],'3.3333')
