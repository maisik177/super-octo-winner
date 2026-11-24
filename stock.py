"""IdoSell stock editor. Python standard library only."""
import json
import math
import os
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parent
SHOP = 'kartony24h.com'
class ApiError(Exception): pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def errors(value):
    if isinstance(value, dict):
        if value.get('faultCode') not in (None, '', 0, '0'):
            raise ApiError(str(value.get('faultString', 'Błąd API')))
        if value.get('isErrors'): raise ApiError('API zgłosiło błąd operacji.')
        for v in value.values(): errors(v)
    elif isinstance(value, list):
        for v in value: errors(v)


def quantity(value):
    try: n = float(str(value).strip().replace(',', '.'))
    except ValueError: raise ApiError('Podaj prawidłową ilość.')
    if not math.isfinite(n) or n < 0: raise ApiError('Ilość musi być skończoną liczbą nieujemną.')
    return n


class Api:
    def __init__(self, key):
        self.key = key.strip()
        if not self.key: raise ApiError('Brak klucza API.')
        self.opener = urllib.request.build_opener(NoRedirect)

    def call(self, endpoint, method='GET', body=None, params=None):
        url = f'https://{SHOP}/api/admin/v8/{endpoint}'
        if params: url += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-API-KEY': self.key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.opener.open(req, timeout=40) as r: result=json.load(r)
        except urllib.error.HTTPError as e:
            raise ApiError(f'HTTP {e.code}. Sprawdź klucz i uprawnienia API.') from None
        except (OSError, ValueError) as e:
            raise ApiError('Brak potwierdzenia odpowiedzi API. Po próbie zapisu odczytaj stan przed ponowieniem.') from None
        if not isinstance(result, dict): raise ApiError('Nieoczekiwana odpowiedź API.')
        errors(result)
        return result

    def lookup(self, code):
        code = code.strip()
        if not code or ',' in code: raise ApiError('Wpisz jeden kod zewnętrzny (bez przecinka).')
        data=self.call('products/products', params={'productIds':code})
        rows=[]
        for p in data.get('results', []):
            names=p.get('productDescriptionsLangData', [])
            name=next((n.get('productName') for n in names if n.get('langId')=='pol'), str(p['productId']))
            for stock in p.get('productStocksData', {}).get('productStocksQuantities', []):
                for size in stock.get('productSizesData', []):
                    if size.get('productSizeCodeExternal') == code:
                        rows.append(dict(product_id=p['productId'], name=name, code=code,
                            size=str(size['sizeId']), stock=int(stock['stockId']),
                            quantity=size['productSizeQuantity']))
            for attr in p.get('productSizesAttributes', []):
                if attr.get('productSizeCodeExternal') != code: continue
                for loc in p.get('productStocksData', {}).get('productSizesStocksLocations', []):
                    sid=int(loc['stockId'])
                    if not any(r['product_id']==p['productId'] and r['size']==str(attr['sizeId']) and r['stock']==sid for r in rows):
                        rows.append(dict(product_id=p['productId'], name=name, code=code,
                            size=str(attr['sizeId']),stock=sid,quantity=None))
        if not rows: raise ApiError('Nie znaleziono dokładnie tego kodu zewnętrznego ze stanem magazynowym.')
        if len({(r['product_id'],r['size']) for r in rows}) != 1:
            raise ApiError('Kod nie jest jednoznaczny — zapis zablokowany.')
        return rows

    def update(self, row, new):
        new=quantity(new)
        fresh=next((r for r in self.lookup(row['code']) if r['stock']==row['stock']), None)
        if fresh != row: raise ApiError('Dane zmieniły się. Wyszukaj produkt ponownie.')
        self.call('products/stockQuantity','PUT',{'params':{'products':[{
            'productSizeCodeExternal':row['code'], 'stockId':row['stock'], 'productSizeQuantity':new}]}})
        after=next((r for r in self.lookup(row['code']) if r['stock']==row['stock']),None)
        if after is None or after['quantity'] is None or float(after['quantity']) != new:
            raise ApiError('Zapis wysłano, lecz odczyt nie potwierdził ilości. Odśwież stan; nie ponawiaj w ciemno.')
        return after

    def product_by_external(self, code):
        code=code.strip()
        if not code or ',' in code: raise ApiError('Wpisz jeden kod zewnętrzny.')
        found=[p for p in self.call('products/products',params={'productIds':code}).get('results',[])
            if any(a.get('productSizeCodeExternal')==code for a in p.get('productSizesAttributes',[]))]
        if len(found)!=1: raise ApiError('Nie znaleziono jednoznacznego kodu zewnętrznego.')
        return found[0]

    def bundles(self, code):
        source=self.product_by_external(code)
        ids=list(dict.fromkeys(source.get('bundledIds',[])))
        products=[]
        for start in range(0,len(ids),100):
            batch=ids[start:start+100]
            result=self.call('products/products',params={'productIds':','.join(map(str,batch))}).get('results',[])
            wanted=set(map(str,batch))
            result=[p for p in result if str(p.get('productId')) in wanted]
            if {str(p['productId']) for p in result} != wanted:
                raise ApiError('API nie zwróciło wszystkich zestawów. Odśwież listę.')
            products.extend(result)
        rows=[]
        for p in products:
            if p.get('productType')!='product_bundle': continue
            rows.append(self.bundle_row(p,code,source['productId']))
        return rows

    @staticmethod
    def bundle_row(p,code,source_id):
        name=next((n.get('productName') for n in p.get('productDescriptionsLangData',[]) if n.get('langId')=='pol'),str(p['productId']))
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        pieces=None; unit_price=None
        items=p.get('productBundleItems') or []
        try:
            amounts=[Decimal(str(item['bundleQuantity'])) for item in items]
            if amounts and all(n.is_finite() and n>0 for n in amounts):
                total=sum(amounts)
                pieces=format(total,'f').rstrip('0').rstrip('.') if '.' in format(total,'f') else format(total,'f')
                price=Decimal(str(p.get('productRetailPrice')))
                if price.is_finite() and price>=0:
                    unit_price=format((price/total).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP),'f')
        except (KeyError, InvalidOperation, TypeError, ValueError):
            pass
        return {'pieces':pieces,'unit_price':unit_price,'product_id':p['productId'],'name':name,'code':', '.join(str(a.get('productSizeCodeExternal','')) for a in p.get('productSizesAttributes',[])),
            'price':p.get('productRetailPrice'),'source_code':code,'source_id':source_id}

    def update_bundle_price(self,row,value):
        from decimal import Decimal, InvalidOperation
        try: price=Decimal(str(value).strip().replace(',','.'))
        except InvalidOperation: raise ApiError('Nieprawidłowa cena.')
        if not price.is_finite() or price<0 or price!=price.quantize(Decimal('0.01')):
            raise ApiError('Cena musi być nieujemna i mieć najwyżej 2 miejsca po przecinku.')
        source=self.product_by_external(row['source_code'])
        if str(source['productId'])!=str(row['source_id']) or str(row['product_id']) not in map(str,source.get('bundledIds',[])):
            raise ApiError('Zmieniło się przypisanie zestawu. Pobierz listę ponownie.')
        def read_bundle():
            bundle_id=str(row['product_id'])
            products=self.call('products/products',params={'productIds':bundle_id}).get('results',[])
            matches=[p for p in products if str(p.get('productId'))==bundle_id]
            if len(matches)!=1 or matches[0].get('productType')!='product_bundle':
                raise ApiError(f'Nie udało się potwierdzić zestawu o ID {bundle_id}.')
            return matches[0]

        def retail_price(product):
            try: amount=Decimal(str(product.get('productRetailPrice')))
            except InvalidOperation: raise ApiError('Brak prawidłowej ceny zestawu w danych API.')
            if not amount.is_finite(): raise ApiError('Brak prawidłowej ceny zestawu w danych API.')
            return amount

        current=retail_price(read_bundle())
        previous=retail_price({'productRetailPrice':row['price']})
        if current!=previous:
            raise ApiError(f'Cena zestawu zmieniła się z {previous} na {current}. Pobierz listę ponownie.')
        self.call('products/products','PUT',{'params':{'products':[{'productId':row['product_id'],
            'priceChangeMode':'amount_set','productRetailPrice':float(price)}]}})
        result=read_bundle()
        if retail_price(result)!=price:
            raise ApiError('Zapis wysłano, ale cena nie została potwierdzona odczytem. Odśwież listę.')
        return self.bundle_row(result,row['source_code'],row['source_id'])
