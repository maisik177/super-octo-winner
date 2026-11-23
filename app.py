import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from stock import Api, ApiError, quantity
from credentials import load_key, save_key

class App:
    def __init__(self, root):
        self.root=root; self.events=queue.Queue(); self.busy=False; self.rows=[]
        root.title('IdoSell — stany magazynowe | kartony24h.com')
        root.geometry('1000x700'); root.minsize(850,600)
        frame=ttk.Frame(root,padding=20); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Zmiana stanu magazynowego',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(frame,text='kartony24h.com · nowa ilość zastępuje dotychczasowy stan').pack(anchor='w',pady=(0,12))
        ttk.Button(frame,text='Importuj klucz API…',command=self.import_key).pack(anchor='e')
        line=ttk.Frame(frame); line.pack(fill='x',pady=8)
        ttk.Label(line,text='Kod zewnętrzny:').pack(side='left')
        self.code=ttk.Entry(line,width=36); self.code.pack(side='left',padx=8)
        self.code.bind('<Return>',lambda e:self.search())
        ttk.Button(line,text='Wyszukaj / odśwież',command=self.search).pack(side='left')
        self.tree=ttk.Treeview(frame,columns=('id','name','size','stock','quantity'),show='headings',height=7,selectmode='browse')
        for c,t,w in [('id','ID',60),('name','Produkt',310),('size','Wariant',70),('stock','Magazyn ID',90),('quantity','Stan',100)]:
            self.tree.heading(c,text=t); self.tree.column(c,width=w)
        self.tree.pack(fill='both',expand=True)
        line=ttk.Frame(frame); line.pack(fill='x',pady=12)
        ttk.Label(line,text='Nowa ilość:').pack(side='left')
        self.amount=ttk.Entry(line,width=15); self.amount.pack(side='left',padx=8)
        ttk.Button(line,text='Ustaw ilość…',command=self.update).pack(side='left')
        self.status=tk.StringVar(value='Wpisz kod i wybierz magazyn. Przy pierwszym uruchomieniu zaimportuj klucz API.')
        ttk.Label(frame,textvariable=self.status,wraplength=760).pack(anchor='w')
        self.build_bundles(frame)
        root.after(100,self.drain)
    def build_bundles(self,frame):
        self.bundle_rows=[]
        ttk.Separator(frame).pack(fill='x',pady=10)
        ttk.Label(frame,text='Ceny detaliczne brutto zestawów',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Kod powyżej wskazuje składnik. Pobierz wszystkie jego zestawy, zaznacz wiersze i ustaw cenę całego zestawu.').pack(anchor='w')
        ttk.Button(frame,text='Pobierz wszystkie zestawy produktu',command=self.search_bundles).pack(anchor='w',pady=5)
        self.bundle_tree=ttk.Treeview(frame,columns=('id','code','name','pieces','price','unit_price'),show='headings',height=6,selectmode='extended')
        for c,t,w in [('id','ID',60),('code','Kod zestawu',120),('name','Zestaw',330),('pieces','Liczba sztuk',95),('price','Cena brutto',110),('unit_price','Brutto / szt.',115)]:
            self.bundle_tree.heading(c,text=t);self.bundle_tree.column(c,width=w)
        self.bundle_tree.pack(fill='both',expand=True)
        line=ttk.Frame(frame);line.pack(fill='x',pady=8)
        ttk.Button(line,text='Zaznacz wszystkie',command=lambda:self.bundle_tree.selection_set(self.bundle_tree.get_children())).pack(side='left')
        ttk.Label(line,text=' Nowa cena brutto: ').pack(side='left')
        self.price=ttk.Entry(line,width=12);self.price.pack(side='left')
        ttk.Button(line,text='Zapisz cenę zaznaczonych…',command=self.save_prices).pack(side='left',padx=8)
    def show_bundles(self,rows):
        self.bundle_rows=rows;self.bundle_tree.delete(*self.bundle_tree.get_children())
        for i,r in enumerate(rows):
            self.bundle_tree.insert('','end',iid=str(i),values=(r['product_id'],r['code'],r['name'],r.get('pieces') or 'brak danych',r['price'],r.get('unit_price') or 'brak danych'))
        self.status.set(f'Pobrano wszystkie zestawy: {len(rows)}. Ctrl / Shift pozwala zaznaczyć kilka. Cena / szt. = cena zestawu ÷ suma sztuk składników.')
    def search_bundles(self):
        if self.busy:return
        code=self.code.get().strip();self.show_bundles([])
        self.run(lambda:Api(load_key()).bundles(code),self.show_bundles)
    def save_prices(self):
        if self.busy:return
        selected=[dict(self.bundle_rows[int(i)]) for i in self.bundle_tree.selection()]
        if not selected:messagebox.showinfo('Zestawy','Zaznacz zestawy do zmiany ceny.');return
        if any(r['source_code']!=self.code.get().strip() for r in selected):
            messagebox.showinfo('Kod zmieniony','Pobierz zestawy ponownie.');return
        from decimal import Decimal,InvalidOperation
        try:
            value=Decimal(self.price.get().strip().replace(',','.'))
            if not value.is_finite() or value<0 or value!=value.quantize(Decimal('0.01')):raise InvalidOperation
        except InvalidOperation:messagebox.showerror('Cena','Podaj nieujemną cenę z maksymalnie 2 miejscami po przecinku.');return
        preview='\n'.join(f"ID {r['product_id']} | {r['code']} | {r['price']} → {value}" for r in selected)
        if not messagebox.askyesno('Potwierdź ceny zestawów',f'Ustawić tę samą cenę brutto dla {len(selected)} zestawów?\n\n'+preview):return
        def work():
            api=Api(load_key());done=[];failure=None
            for row in selected:
                try:done.append(api.update_bundle_price(row,str(value)))
                except Exception as e:failure=f"ID {row['product_id']}: {e}";break
            return done,failure
        def finish(result):
            done,failure=result
            replacements={r['product_id']:r for r in done}
            self.show_bundles([replacements.get(r['product_id'],r) for r in self.bundle_rows])
            self.status.set(f'Potwierdzono zapis {len(done)} z {len(selected)} zestawów.' + (' Przerwano: '+failure if failure else ''))
            if failure:messagebox.showerror('Zapis przerwany',f'Potwierdzone zmiany: {len(done)}. Pozostałych nie ponawiano.\n'+failure)
        self.run(work,finish)
    def run(self, fn, done):
        if self.busy: return
        self.busy=True; self.status.set('Trwa operacja API…')
        def worker():
            try: self.events.put((done,fn(),None))
            except Exception as e: self.events.put((done,None,str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def drain(self):
        try:
            done,result,error=self.events.get_nowait(); self.busy=False
            if error:
                self.status.set(error); messagebox.showerror('Operacja niepotwierdzona',error)
            else: done(result)
        except queue.Empty: pass
        self.root.after(100,self.drain)
    def show(self, rows):
        self.rows=rows
        self.tree.delete(*self.tree.get_children())
        for i,r in enumerate(rows):
            self.tree.insert('', 'end', iid=str(i),values=(r['product_id'],r['name'],r['size'],r['stock'],r['quantity'] if r['quantity'] is not None else 'brak danych'))
        self.status.set('Wybierz magazyn i wpisz nową ilość. „Brak danych” nie oznacza zera.')
    def search(self):
        if self.busy:return
        code=self.code.get().strip()
        self.rows=[]; self.tree.delete(*self.tree.get_children())
        self.run(lambda:Api(load_key()).lookup(code),self.show)
    def update(self):
        if self.busy:return
        selection=self.tree.selection()
        if not selection: messagebox.showinfo('Magazyn','Wybierz wiersz magazynu.'); return
        row=dict(self.rows[int(selection[0])])
        if self.code.get().strip()!=row['code']:
            messagebox.showinfo('Kod zmieniony','Wyszukaj ponownie wpisany kod.'); return
        try:new=quantity(self.amount.get())
        except ApiError as e: messagebox.showerror('Ilość',str(e)); return
        old=row['quantity'] if row['quantity'] is not None else 'brak danych'
        if not messagebox.askyesno('Potwierdź zmianę',f"{row['name']}\nKod: {row['code']}\nMagazyn: {row['stock']}\nStan: {old} → {new}\n\nUstawić nową ilość?"):return
        def done(after):
            self.show([after]); self.status.set(f"Zapis potwierdzony ponownym odczytem: {after['quantity']}.")
        self.run(lambda:Api(load_key()).update(row,new),done)
    def import_key(self):
        if self.busy:return
        p=filedialog.askopenfilename(title='Plik tekstowy z kluczem API')
        if not p:return
        try:save_key(Path(p).read_text(encoding='utf-8-sig')); self.status.set('Klucz zapisany przez Windows DPAPI.')
        except Exception as e:messagebox.showerror('Klucz',str(e))
if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()
