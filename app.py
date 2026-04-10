import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import askstring
import webbrowser

from db import (
    init_db, get_user_count, authenticate, create_user,
    create_product, record_transaction, get_inventory, update_product_count,
    update_pin, delete_user, delete_product, get_user_summary,
    start_scheduled_backups, stop_scheduled_backups,
)
from admin import export_pdf, export_users_pdf, export_inventory_pdf
from utils import fetch_product_name_online


# ---------------------------------------------------------------------------
# Application root
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Getraenkekeller")
        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        init_db()
        start_scheduled_backups()
        self.user = None  # (id, name, is_admin) after login

        self.frames: dict[type, tk.Frame] = {}
        for FrameCls in (SetupFrame, LoginFrame, UserFrame, AdminFrame):
            frm = FrameCls(self)
            self.frames[FrameCls] = frm
            frm.place(relwidth=1, relheight=1)

        self._show_initial()

    def show_frame(self, frame_cls: type):
        frm = self.frames[frame_cls]
        frm.tkraise()
        frm.on_show()

    def _on_close(self):
        stop_scheduled_backups()
        self.destroy()

    def _show_initial(self):
        if get_user_count() == 0:
            self.show_frame(SetupFrame)
        else:
            self.show_frame(LoginFrame)


# ---------------------------------------------------------------------------
# First-run setup
# ---------------------------------------------------------------------------

class SetupFrame(tk.Frame):
    def __init__(self, master: App):
        super().__init__(master)
        ttk.Label(self, text="Erster Admin anlegen", font=("Arial", 24)).pack(pady=20)
        self.pin_entry = ttk.Entry(self, show="*")
        self.pin_entry.pack(pady=5)
        self.pin_entry.insert(0, "PIN eingeben")
        self.name_entry = ttk.Entry(self)
        self.name_entry.pack(pady=5)
        self.name_entry.insert(0, "Name")
        self.pin_entry.bind("<Return>", lambda _e: self._create())
        self.name_entry.bind("<Return>", lambda _e: self._create())
        ttk.Button(self, text="Anlegen", command=self._create).pack(pady=10)

    def _create(self):
        pin = self.pin_entry.get().strip()
        name = self.name_entry.get().strip()
        if not pin or not name:
            messagebox.showerror("Fehler", "PIN und Name duerfen nicht leer sein", parent=self)
            return
        try:
            create_user(pin, name, is_admin=True)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc), parent=self)
            return
        messagebox.showinfo("OK", "Admin angelegt", parent=self)
        self.master.show_frame(LoginFrame)

    def on_show(self):
        self.pin_entry.focus_set()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginFrame(tk.Frame):
    def __init__(self, master: App):
        super().__init__(master)
        ttk.Label(self, text="Login (PIN)", font=("Arial", 24)).pack(pady=20)
        self.pin_entry = ttk.Entry(self, show="*")
        self.pin_entry.pack(pady=5)
        self.pin_entry.bind("<Return>", lambda _e: self._login())
        ttk.Button(self, text="Login", command=self._login).pack(pady=10)

    def _login(self):
        pin = self.pin_entry.get().strip()
        auth = authenticate(pin)
        if not auth:
            messagebox.showerror("Fehler", "Ungueltiger PIN", parent=self)
            return
        self.master.user = auth
        if auth[2]:  # is_admin
            self.master.show_frame(AdminFrame)
        else:
            self.master.show_frame(UserFrame)

    def on_show(self):
        self.pin_entry.delete(0, tk.END)
        self.pin_entry.focus_set()


# ---------------------------------------------------------------------------
# Regular user: scan & book
# ---------------------------------------------------------------------------

class UserFrame(tk.Frame):
    LOGOUT_TIMEOUT_MS = 20_000

    def __init__(self, master: App):
        super().__init__(master)
        ttk.Label(self, text="Barcode scannen", font=("Arial", 24)).pack(pady=20)

        self.barcode_entry = ttk.Entry(self)
        self.barcode_entry.pack(pady=5)
        self.barcode_entry.bind("<Return>", lambda _e: self._book())

        self.qty_entry = ttk.Entry(self, width=5)
        self.qty_entry.pack(pady=5)
        self.qty_entry.insert(0, "1")
        self.qty_entry.bind("<Return>", lambda _e: self._set_multi())

        ttk.Button(self, text="Buchen", command=self._book).pack(pady=10)
        ttk.Button(self, text="Naechster Scan xN", command=self._set_multi).pack(pady=5)
        ttk.Button(
            self, text="Logout",
            command=lambda: master.show_frame(LoginFrame),
        ).pack(side="bottom", pady=20)

        self.next_qty = 1
        self.summary_var = tk.StringVar()
        tk.Label(
            self, textvariable=self.summary_var, justify="center", anchor="center",
        ).pack(pady=5, fill="x", padx=20)

        self._logout_after_id = None

    # -- helpers --

    def _restart_timer(self):
        if self._logout_after_id:
            self.after_cancel(self._logout_after_id)
        self._logout_after_id = self.after(
            self.LOGOUT_TIMEOUT_MS,
            lambda: self.master.show_frame(LoginFrame),
        )

    def _set_multi(self):
        try:
            self.next_qty = max(1, int(self.qty_entry.get()))
            messagebox.showinfo(
                "OK", f"Naechster Scan wird {self.next_qty}-mal gebucht", parent=self,
            )
            self.barcode_entry.focus_set()
        except ValueError:
            messagebox.showerror("Fehler", "Ungueltige Zahl", parent=self)

    def _book(self):
        bc = self.barcode_entry.get().strip()
        try:
            record_transaction(self.master.user[0], bc, self.next_qty)
            self.next_qty = 1
            self.qty_entry.delete(0, tk.END)
            self.qty_entry.insert(0, "1")
            messagebox.showinfo("OK", "Buchung erfolgreich", parent=self)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self)
        self.barcode_entry.delete(0, tk.END)
        self.barcode_entry.focus_set()
        self._update_summary()
        self._restart_timer()

    def _update_summary(self):
        summary = get_user_summary(self.master.user[0])
        if summary:
            text = "\n".join(f"{name}: {cnt}" for name, cnt in summary)
        else:
            text = "Keine Buchungen vorhanden."
        self.summary_var.set(text)

    def on_show(self):
        self.barcode_entry.delete(0, tk.END)
        self.qty_entry.delete(0, tk.END)
        self.qty_entry.insert(0, "1")
        self.next_qty = 1
        self._update_summary()
        self.barcode_entry.focus_set()
        self._restart_timer()


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------

class AdminFrame(tk.Frame):
    def __init__(self, master: App):
        super().__init__(master)
        buttons = [
            ("Neuen User",          self._new_user),
            ("Neues Produkt",       self._new_prod),
            ("Bestand anzeigen",    self._show_inv),
            ("Bestand bearbeiten",  self._edit_inv),
            ("User loeschen",       self._del_user),
            ("Produkt loeschen",    self._del_prod),
            ("PDF exportieren",     self._export),
            ("Userliste PDF",       self._export_users),
            ("Produktliste PDF",    self._export_inv),
            ("PIN aendern",         self._edit_pin),
            ("Logout",              lambda: master.show_frame(LoginFrame)),
        ]
        for text, cmd in buttons:
            ttk.Button(self, text=text, command=cmd).pack(fill="x", pady=5, padx=20)

    def on_show(self):
        pass

    # -- user management --

    def _new_user(self):
        root = self.winfo_toplevel()
        pin = askstring("User anlegen", "PIN:", parent=root)
        name = askstring("User anlegen", "Name:", parent=root)
        adm = messagebox.askyesno("User anlegen", "Soll Admin sein?", parent=root)
        if pin and name:
            try:
                create_user(pin, name, adm)
                messagebox.showinfo("OK", "User angelegt", parent=self)
            except ValueError as exc:
                messagebox.showerror("Fehler", str(exc), parent=self)

    def _del_user(self):
        root = self.winfo_toplevel()
        name = askstring("User loeschen", "Name:", parent=root)
        if not name:
            return
        if name == self.master.user[1]:
            messagebox.showerror("Fehler", "Eigenen Account kann man nicht loeschen", parent=root)
            return
        if not messagebox.askyesno("Bestaetigung", f"{name} wirklich loeschen?", parent=root):
            return
        try:
            delete_user(name, self.master.user[0])
            messagebox.showinfo("OK", "User geloescht", parent=root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)

    def _edit_pin(self):
        root = self.winfo_toplevel()
        username = askstring("PIN aendern", "Name:", parent=root)
        if not username:
            return
        new_pin = askstring("PIN aendern", "Neuer PIN:", parent=root)
        if not new_pin:
            return
        try:
            update_pin(username, new_pin)
            messagebox.showinfo("OK", "PIN aktualisiert", parent=root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)

    # -- product management --

    def _new_prod(self):
        root = self.winfo_toplevel()
        bc = askstring("Produkt", "Barcode:", parent=root)
        if not bc:
            return
        try:
            name = fetch_product_name_online(bc)
            messagebox.showinfo("Online", "Gefunden: " + name, parent=root)
        except Exception:
            name = askstring("Produkt", "Name manuell:", parent=root)
        cnt = askstring("Produkt", "Anfangsbestand (Zahl):", parent=root) or "0"
        try:
            create_product(bc, name, int(cnt))
            messagebox.showinfo("OK", "Produkt angelegt", parent=root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)

    def _show_inv(self):
        inv = get_inventory()
        text = "\n".join(
            f"{pid}: {name} ({barcode}) - Bestand: {count}"
            for pid, barcode, name, count in inv
        )
        messagebox.showinfo("Inventar", text or "Keine Produkte", parent=self)

    def _edit_inv(self):
        root = self.winfo_toplevel()
        bc = askstring("Bearbeiten", "Barcode:", parent=root)
        if not bc:
            return
        nc = askstring("Bearbeiten", "Neuer Bestand:", parent=root)
        try:
            update_product_count(bc, int(nc))
            messagebox.showinfo("OK", "Bestand aktualisiert", parent=root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)

    def _del_prod(self):
        root = self.winfo_toplevel()
        bc = askstring("Produkt loeschen", "Barcode:", parent=root)
        if not bc:
            return
        if not messagebox.askyesno("Bestaetigung", f"Produkt {bc} loeschen?", parent=root):
            return
        try:
            delete_product(bc)
            messagebox.showinfo("OK", "Produkt geloescht", parent=root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)

    # -- PDF exports --

    def _export(self):
        export_pdf()
        messagebox.showinfo("OK", "report.pdf erstellt", parent=self)
        webbrowser.open("report.pdf")

    def _export_users(self):
        export_users_pdf()
        messagebox.showinfo("OK", "users.pdf erstellt", parent=self)
        webbrowser.open("users.pdf")

    def _export_inv(self):
        export_inventory_pdf()
        messagebox.showinfo("OK", "inventory.pdf erstellt", parent=self)
        webbrowser.open("inventory.pdf")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    App().mainloop()
