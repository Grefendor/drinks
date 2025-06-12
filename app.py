import tkinter as tk
from tkinter import ttk, messagebox
import requests
import webbrowser
from db import (
    init_db, get_user_count, authenticate, create_user,
    create_product, record_transaction, get_inventory, update_product_count,
    update_pin, delete_user, delete_product, get_user_summary
)
from admin import export_pdf, export_users_pdf, export_inventory_pdf

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
        self.pin = ttk.Entry(self, show="*")
        self.pin.pack(pady=5)
        self.pin.insert(0, "PIN eingeben")
        self.name = ttk.Entry(self)
        self.name.pack(pady=5)
        self.name.insert(0, "Name")
        self.pin.focus_set()
        self.pin.bind("<Return>", lambda e: self._create())
        self.name.bind("<Return>", lambda e: self._create())
        ttk.Button(self, text="Anlegen", command=self._create).pack(pady=10)

    def _create(self):
        pin = self.pin.get().strip()
        name = self.name.get().strip()
        if not pin or not name:
            messagebox.showerror("Fehler","PIN und Name dürfen nicht leer sein", parent=self)
            return
        try:
            create_user(pin,name,True)
        except ValueError as e:
            messagebox.showerror("Fehler",str(e), parent=self)
            return
        messagebox.showinfo("OK","Admin angelegt", parent=self)
        self.master._show_frame(LoginFrame)

    def on_show(self):
        self.pin.focus_set()

class LoginFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        ttk.Label(self, text="Login (PIN)", font=("Arial",24)).pack(pady=20)
        self.pin = ttk.Entry(self, show="*")
        self.pin.pack(pady=5)
        self.pin.bind("<Return>", lambda e: self._login())
        ttk.Button(self, text="Login", command=self._login).pack(pady=10)

    def _login(self):
        pin = self.pin.get().strip()
        auth = authenticate(pin)
        if not auth:
            messagebox.showerror("Fehler","Ungültiger PIN", parent=self)
            return
        self.master.user = auth
        if auth[2]:
            self.master._show_frame(AdminFrame)
        else:
            self.master._show_frame(UserFrame)

    def on_show(self):
        self.pin.delete(0,tk.END)
        self.pin.focus_set()

class UserFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        ttk.Label(self, text="Barcode scannen", font=("Arial",24)).pack(pady=20)
        self.entry = ttk.Entry(self)
        self.entry.pack(pady=5)
        self.entry.focus()
        self.entry.bind("<Return>", lambda e: self._book())
        self.qty = ttk.Entry(self, width=5)
        self.qty.pack(pady=5)
        self.qty.insert(0, "1")
        self.qty.bind("<Return>", lambda e: self._set_multi())
        ttk.Button(self, text="Buchen", command=self._book).pack(pady=10)
        ttk.Button(self, text="N\u00e4chster Scan xN", command=self._set_multi).pack(pady=5)
        ttk.Button(self, text="Logout", command=lambda: master._show_frame(LoginFrame)).pack(side="bottom", pady=20)
        self.next_qty = 1
        self.summary_var = tk.StringVar()
        tk.Label(
            self,
            textvariable=self.summary_var,
            justify="center",
            anchor="center",
        ).pack(pady=5, fill="x", padx=20)
        self.logout_after_id = None

    def _restart_timer(self):
        if self.logout_after_id:
            self.after_cancel(self.logout_after_id)
        self.logout_after_id = self.after(20000, lambda: self.master._show_frame(LoginFrame))

    def _set_multi(self):
        try:
            self.next_qty = max(1, int(self.qty.get()))
            messagebox.showinfo("OK", f"N\u00e4chster Scan wird {self.next_qty}-mal gebucht", parent=self)
            self.entry.focus_set()
        except ValueError:
            messagebox.showerror("Fehler", "Ung\u00fcltige Zahl", parent=self)

    def _book(self):
        bc = self.entry.get().strip()
        try:
            record_transaction(self.master.user[0], bc, self.next_qty)
            self.next_qty = 1
            self.qty.delete(0, tk.END)
            self.qty.insert(0, "1")
            messagebox.showinfo("OK","Buchung erfolgreich", parent=self)
        except Exception as e:
            messagebox.showerror("Fehler",str(e), parent=self)
        self.entry.delete(0,tk.END)
        self.entry.focus_set()
        self._restart_timer()

    def on_show(self):
        self.entry.delete(0,tk.END)
        self.qty.delete(0, tk.END)
        self.qty.insert(0, "1")
        self.next_qty = 1
        summary = get_user_summary(self.master.user[0])
        if summary:
            text = "\n".join(f"{n}: {c}" for n, c in summary)
        else:
            text = "Keine Buchungen vorhanden."
        self.summary_var.set(text)
        self.entry.focus()
        self._restart_timer()

class AdminFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        btns = [
            ("Neuen User", self._new_user),
            ("Neues Produkt", self._new_prod),
            ("Bestand anzeigen", self._show_inv),
            ("Bestand bearbeiten", self._edit_inv),
            ("User löschen", self._del_user),
            ("Produkt löschen", self._del_prod),
            ("PDF exportieren", self._export),
            ("Userliste PDF", self._export_users),
            ("Produktliste PDF", self._export_inv),
            ("PIN ändern", self._edit_pin),
            ("Logout", lambda: master._show_frame(LoginFrame))
        ]
        for t,cmd in btns:
            ttk.Button(self, text=t, command=cmd).pack(fill="x", pady=5, padx=20)

    def on_show(self): pass

    def _new_user(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        pin = askstring("User anlegen", "PIN:", parent=root)
        name = askstring("User anlegen", "Name:", parent=root)
        adm = messagebox.askyesno("User anlegen", "Soll Admin sein?", parent=root)
        if pin and name:
            try:
                create_user(pin, name, adm)
            except ValueError as e:
                return messagebox.showerror("Fehler", str(e), parent=self)
            messagebox.showinfo("OK", "User angelegt", parent=self)

    def _new_prod(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        bc = askstring("Produkt", "Barcode:", parent=root)
        if not bc:
            return
        try:
            name = fetch_product_name_online(bc)
            messagebox.showinfo("Online", "Gefunden: "+name, parent=root)
        except Exception:
            name = askstring("Produkt", "Name manuell:", parent=root)
        cnt = askstring("Produkt", "Anfangsbestand (Zahl):", parent=root) or "0"
        try:
            cnt = int(cnt)
            create_product(bc,name,cnt)
            messagebox.showinfo("OK", "Produkt angelegt", parent=root)
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=root)

    def _show_inv(self):
        inv = get_inventory()
        text = "\n".join(
            f"{i}: {n} ({b}) - Bestand: {c}" for i, b, n, c in inv
        )
        messagebox.showinfo("Inventar", text or "Keine Produkte", parent=self)

    def _edit_inv(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        bc = askstring("Bearbeiten", "Barcode:", parent=root)
        if not bc:
            return
        nc = askstring("Bearbeiten", "Neuer Bestand:", parent=root)
        try:
            update_product_count(bc,int(nc))
            messagebox.showinfo("OK", "Bestand aktualisiert", parent=root)
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=root)

    def _del_user(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        name = askstring("User löschen", "Name:", parent=root)
        if not name:
            return
        if name == self.master.user[1]:
            return messagebox.showerror(
                "Fehler", "Eigenen Account kann man nicht löschen", parent=root
            )
        if not messagebox.askyesno(
            "Bestätigung", f"{name} wirklich löschen?", parent=root
        ):
            return
        try:
            delete_user(name, self.master.user[0])
            messagebox.showinfo("OK", "User gelöscht", parent=root)
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=root)

    def _del_prod(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        bc = askstring("Produkt löschen", "Barcode:", parent=root)
        if not bc:
            return
        if not messagebox.askyesno(
            "Bestätigung", f"Produkt {bc} löschen?", parent=root
        ):
            return
        try:
            delete_product(bc)
            messagebox.showinfo("OK", "Produkt gelöscht", parent=root)
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=root)

    def _edit_pin(self):
        from tkinter.simpledialog import askstring
        root = self.winfo_toplevel()
        username = askstring("Bearbeiten", "Name:", parent=root)
        if not username:
            return
        new_pin = askstring("Bearbeiten", "Neuer PIN:", parent=root)
        try:
            update_pin(username, new_pin)
            messagebox.showinfo("OK", "PIN aktualisiert", parent=root)
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=root)

    def _export(self):
        export_pdf()
        messagebox.showinfo("OK","report.pdf erstellt", parent=self)
        webbrowser.open("report.pdf")

    def _export_users(self):
        export_users_pdf()
        messagebox.showinfo("OK", "users.pdf erstellt", parent=self)
        webbrowser.open("users.pdf")

    def _export_inv(self):
        export_inventory_pdf()
        messagebox.showinfo("OK", "inventory.pdf erstellt", parent=self)
        webbrowser.open("inventory.pdf")

if __name__ == "__main__":
    App().mainloop()
