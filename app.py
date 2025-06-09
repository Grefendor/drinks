import tkinter as tk
from tkinter import ttk, messagebox
import requests
import webbrowser
from db import (
    init_db, get_user_count, authenticate, create_user,
    create_product, record_transaction, get_inventory, update_product_count
)
from admin import export_pdf

def fetch_product_name_online(barcode: str) -> str:
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == 1 and data["product"].get("product_name"):
        return data["product"]["product_name"]
    raise RuntimeError("Nicht in OpenFoodFacts gefunden")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Getränkekeller")
        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self.destroy())
        init_db()
        self.user = None
        self._build_frames()
        self._show_initial()

    def _build_frames(self):
        self.frames = {}
        for F in (SetupFrame, LoginFrame, UserFrame, AdminFrame):
            frm = F(self)
            self.frames[F] = frm
            frm.place(relwidth=1, relheight=1)

    def _show_frame(self, frame_cls):
        frm = self.frames[frame_cls]
        frm.tkraise()
        frm.on_show()

    def _show_initial(self):
        if get_user_count() == 0:
            self._show_frame(SetupFrame)
        else:
            self._show_frame(LoginFrame)

class SetupFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        ttk.Label(self, text="Erster Admin anlegen", font=("Arial",24)).pack(pady=20)
        self.pin = ttk.Entry(self, show="*"); self.pin.pack(pady=5)
        self.pin.insert(0, "PIN eingeben")
        self.name = ttk.Entry(self); self.name.pack(pady=5)
        self.name.insert(0, "Name")
        self.pin.bind("<Return>", lambda e: self._create())
        self.name.bind("<Return>", lambda e: self._create())
        ttk.Button(self, text="Anlegen", command=self._create).pack(pady=10)

    def _create(self):
        pin = self.pin.get().strip()
        name = self.name.get().strip()
        if not pin or not name:
            messagebox.showerror("Fehler","PIN und Name dürfen nicht leer sein")
            return
        try:
            create_user(pin,name,True)
        except ValueError as e:
            messagebox.showerror("Fehler",str(e))
            return
        messagebox.showinfo("OK","Admin angelegt")
        self.master._show_frame(LoginFrame)

    def on_show(self): pass

class LoginFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        ttk.Label(self, text="Login (PIN)", font=("Arial",24)).pack(pady=20)
        self.pin = ttk.Entry(self, show="*"); self.pin.pack(pady=5)
        self.pin.bind("<Return>", lambda e: self._login())
        ttk.Button(self, text="Login", command=self._login).pack(pady=10)

    def _login(self):
        pin = self.pin.get().strip()
        auth = authenticate(pin)
        if not auth:
            messagebox.showerror("Fehler","Ungültiger PIN")
            return
        self.master.user = auth
        if auth[2]:
            self.master._show_frame(AdminFrame)
        else:
            self.master._show_frame(UserFrame)

    def on_show(self):
        self.pin.delete(0,tk.END)

class UserFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        ttk.Label(self, text="Barcode scannen", font=("Arial",24)).pack(pady=20)
        self.entry = ttk.Entry(self); self.entry.pack(pady=5); self.entry.focus()
        self.entry.bind("<Return>", lambda e: self._book())
        ttk.Button(self, text="Buchen", command=self._book).pack(pady=10)
        ttk.Button(self, text="Logout", command=lambda: master._show_frame(LoginFrame)).pack(side="bottom", pady=20)

    def _book(self):
        bc = self.entry.get().strip()
        try:
            record_transaction(self.master.user[0], bc)
            messagebox.showinfo("OK","Buchung erfolgreich")
        except Exception as e:
            messagebox.showerror("Fehler",str(e))
        self.entry.delete(0,tk.END)

    def on_show(self):
        self.entry.delete(0,tk.END)
        self.entry.focus()

class AdminFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        btns = [
            ("Neuen User", self._new_user),
            ("Neues Produkt", self._new_prod),
            ("Bestand anzeigen", self._show_inv),
            ("Bestand bearbeiten", self._edit_inv),
            ("PDF exportieren", lambda: self._export()),
            ("Logout", lambda: master._show_frame(LoginFrame))
        ]
        for t,cmd in btns:
            ttk.Button(self, text=t, command=cmd).pack(fill="x", pady=5, padx=20)

    def on_show(self): pass

    def _new_user(self):
        from tkinter.simpledialog import askstring
        pin = askstring("User anlegen","PIN:")
        name= askstring("User anlegen","Name:")
        adm = messagebox.askyesno("User anlegen","Soll Admin sein?")
        if pin and name:
            try: create_user(pin,name,adm)
            except ValueError as e: return messagebox.showerror("Fehler",str(e))
            messagebox.showinfo("OK","User angelegt")

    def _new_prod(self):
        from tkinter.simpledialog import askstring
        bc = askstring("Produkt","Barcode:")
        if not bc: return
        try:
            name = fetch_product_name_online(bc)
            messagebox.showinfo("Online","Gefunden: "+name)
        except:
            name = askstring("Produkt","Name manuell:")
        cnt = askstring("Produkt","Anfangsbestand (Zahl):") or "0"
        try:
            cnt = int(cnt)
            create_product(bc,name,cnt)
            messagebox.showinfo("OK","Produkt angelegt")
        except Exception as e:
            messagebox.showerror("Fehler",str(e))

    def _show_inv(self):
        inv = get_inventory()
        text = "\n".join(f"{n}: {b} (Bestand: {c})" for b,n,c in inv)
        messagebox.showinfo("Inventar", text or "Keine Produkte")

    def _edit_inv(self):
        from tkinter.simpledialog import askstring
        bc = askstring("Bearbeiten","Barcode:")
        if not bc: return
        nc = askstring("Bearbeiten","Neuer Bestand:")
        try:
            update_product_count(bc,int(nc))
            messagebox.showinfo("OK","Bestand aktualisiert")
        except Exception as e:
            messagebox.showerror("Fehler",str(e))

    def _export(self):
        export_pdf()
        messagebox.showinfo("OK","report.pdf erstellt")
        webbrowser.open("report.pdf")

if __name__ == "__main__":
    App().mainloop()
