#!/usr/bin/env python3
# -- coding: utf-8 --

import gi #librerÃ­a gi para la interfz,versiÃ³n 3 de GTK
gi.require_version('Gtk', '3.0')  # Asegura que GTK 3 se cargue correctamente

import os, csv, pigpio, serial, threading, time, cv2
from pyzbar import pyzbar #decodificacion del QR
from gi.repository import Gtk, Gdk, GLib
from datetime import datetime  # Para registrar hora y fecha del inventario

#Variables globales
STOP_PIN =  17 #este es el pin fisico 11, se usa para las interrupciones en la ESP, manejado con los botones START y STOP
SERIAL_PORT = '/dev/serial0'
BAUDRATE = 115200

cajas_cafe = 0
cajas_banano = 0
cajas_medico = 0
inventario = []  # Guarda tuplas con (producto, hora, fecha)

class ControlWindow(Gtk.Window):#Clase principal control window que es para el manejo de la interfaz
    def __init__(self):
        super().__init__(title="Warehouse control") #titulo de la ventana
        self.set_default_size(1200, 800)
        hb = Gtk.HeaderBar(show_close_button=True, title="Warehouse control") #nombre en la barra de tareas, agregar un boton de cerrar
        self.set_titlebar(hb)
        
        #Contenedor dinamico principal de la ventana
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30, margin=20)
        self.add(main_hbox)
        
        #Panel superior
        left_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_hbox.pack_start(left_vbox, True, True, 0)
        
        # Frame System State, para mostrar ON, OFF y STANDBY y sus respectivos "LEDs"
        state_frame = Gtk.Frame(label="System State")
        state_frame.set_shadow_type(Gtk.ShadowType.IN)
        left_vbox.pack_start(state_frame, False, True, 0)
        state_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20, margin=15)
        state_frame.add(state_box)

        lbl_off = Gtk.Label(label="OFF"); state_box.pack_start(lbl_off, False, False, 0)
        self.box_off = Gtk.Frame(); self.box_off.set_size_request(24,24)
        self.box_off.get_style_context().add_class("state-box-off")
        state_box.pack_start(self.box_off, False, False, 0)

        lbl_on = Gtk.Label(label="ON"); state_box.pack_start(lbl_on, False, False, 0)
        self.box_on = Gtk.Frame(); self.box_on.set_size_request(24,24)
        self.box_on.get_style_context().add_class("state-box")
        state_box.pack_start(self.box_on, False, False, 0)

        lbl_sb = Gtk.Label(label="STANDBY"); state_box.pack_start(lbl_sb, False, False, 0)
        self.box_sb = Gtk.Frame(); self.box_sb.set_size_request(24,24)
        self.box_sb.get_style_context().add_class("state-box")
        state_box.pack_start(self.box_sb, False, False, 0)
        
        #Frame Boxes in Storage, donde estan los titulos y las cajas de escritura que se actualizan con UART
        boxes_frame = Gtk.Frame(label="Boxes in Storage")
        boxes_frame.set_shadow_type(Gtk.ShadowType.IN)
        left_vbox.pack_start(boxes_frame, True, True, 0)
        grid = Gtk.Grid(row_spacing=20, column_spacing=20, margin=15)
        boxes_frame.add(grid)
        self.entries = []
        for i, text in enumerate(["Bananas","Coffee","Medical"]): #Genera 3 cajas no editables, una por producto
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.START)
            lbl.get_style_context().add_class("big-label")
            ent = Gtk.Entry()
            ent.set_text("0")
            ent.set_editable(False)
            ent.get_style_context().add_class("big-entry")
            grid.attach(lbl, 0, i, 1, 1)
            grid.attach(ent, 1, i, 1, 1)
            self.entries.append(ent)

        # Panel derecho: botones START, STOP y Generate report
        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        main_hbox.pack_start(right_vbox, False, False, 0)
        self.btn_start = Gtk.Button(label="START")
        self.btn_start.get_style_context().add_class("start")
        self.btn_start.connect("clicked", self.on_start) #on_start es la instancia relacionada a cuando se presiona el objeto boton START
        right_vbox.pack_start(self.btn_start, False, False, 0)

        self.btn_stop = Gtk.Button(label="STOP")
        self.btn_stop.get_style_context().add_class("stop")
        self.btn_stop.connect("clicked", self.on_stop) #on_stop es la instancia relacionada a cuando se presiona el objeto boton STOP
        right_vbox.pack_start(self.btn_stop, False, False, 0)

        self.btn_report = Gtk.Button(label="Generate report")
        self.btn_report.get_style_context().add_class("report")
        self.btn_report.connect("clicked", self.on_report) #on_report es la instancia relacionada a cuando se presiona el objeto boton STOP
        right_vbox.pack_end(self.btn_report, False, False, 0)

        #inicializa hardware y estado
        self.init_gpio() #control de pines
        self.apply_css()
        self.btn_start.grab_focus()
        self.update_state(off_active=True)

        #hilo serial, abre la comunicacion serial y empieza el serial listener en hilo
        self.ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
        threading.Thread(target=self.serial_listener, daemon=True).start()

        self.connect("destroy", self.on_destroy)
        self.show_all()

    def init_gpio(self): #esto inicializa el daemon de pigpio, configura el pin 17 como salida digital y lo pone en bajo
        self.pi = pigpio.pi()
        if not self.pi.connected:
            print("Warning: pigpio daemon not connected")
        self.pi.set_mode(STOP_PIN, pigpio.OUTPUT)
        self.pi.write(STOP_PIN, 0)

    def on_start(self, _):  #Si se presiona el boton de START, se pone en alto el pin, apaga el LED OFF y enciende el ON
        self.pi.write(STOP_PIN, 1)
        self.update_state(off_active=False)

    def on_stop(self, _): #Hace lo contrario al de arriba
        self.pi.write(STOP_PIN, 0)
        self.update_state(off_active=True)

    def on_report(self, _):
        #genera archivo CSV de inventario
        carpeta = os.path.expanduser("~/informes")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "inventario.csv")
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Producto", "Hora", "Fecha"])
            for prod, hora, fecha in inventario: #escribe todos los productos almacenados en la matriz de inventario
                w.writerow([prod, hora, fecha])
        print(f"Inventario guardado en {ruta}") #comprobacion en consola

    def leer_qr_y_enviar(self): #funcion de lectura de QRs
        global cajas_cafe, cajas_banano, cajas_medico, inventario
        cap = cv2.VideoCapture(0) #usar OpenCV con captura de video
        if not cap.isOpened():
            print("No se pudo abrir la camara")
            return #excepcion

        encontrado = False
        while not encontrado: #seguir intentando hasta que se lea correctamente
            ret, frame = cap.read()
            if not ret:
                break

            barcodes = pyzbar.decode(frame) #decodificar el QR
            for barcode in barcodes:
                qr_data = barcode.data.decode("utf-8")
                #determina producto
                print(f"QR detectado: {qr_data}")
                self.ser.write((qr_data + "\n").encode()) #enviar comando a ESP con el QR leido, siempre lo envia porque esta fuera del if
                print(f"Enviado al ESP32: {qr_data}")

                # Registro de producto y control de inventario
                prod_map = {'11': 'Coffee', '10': 'Bananas', '01': 'Medical'} #codigo del producto
                prod = prod_map.get(qr_data, 'Unknown')
                #solo registrar en inventario y UI si menor a 5
                if prod == 'Coffee' and cajas_cafe < 5:
                    cajas_cafe += 1
                elif prod == 'Bananas' and cajas_banano < 5:
                    cajas_banano += 1
                elif prod == 'Medical' and cajas_medico < 5:
                    cajas_medico += 1
                else:
                    break

                # Agregar a inventario con hora y fecha
                now = datetime.now()
                hora = now.strftime('%H:%M')
                fecha = now.strftime('%d/%m/%Y')
                inventario.append((prod, hora, fecha))
                #actualiza UI usando el hilo principal de la UI 
                GLib.idle_add(self.update_boxes)
                encontrado = True
                break

        cap.release()

    #se encarga de la comunicacion serial y la interpretacion de comandos    
    def serial_listener(self):
        global cajas_cafe, cajas_banano, cajas_medico
        while True:
            try:
                line = self.ser.readline()
            except (serial.SerialException, OSError, TypeError):
                break
            if not line:
                time.sleep(0.1) #pare 0.1 ms 
                continue
            data = line.decode('utf-8', errors='ignore').strip()
            if data == "STBY": #comando para STANDBY, nos envia a la funcion respectiva
                GLib.idle_add(self.on_standby_command)
            elif data == "RUN": #comando run
                GLib.idle_add(self.update_state, False)
            elif data == "SCAN": #comando SCAN para leer qr
                GLib.idle_add(self.leer_qr_y_enviar)
            elif len(data) == 3 and data.isdigit(): #si el string recibido es un numero, decodifiquelo y actualice la interfaz grafica
                cajas_cafe = int(data[0])
                cajas_banano = int(data[1])
                cajas_medico = int(data[2])
                GLib.idle_add(self.update_boxes)
        print("Serial listener stopped")

    def on_standby_command(self): #apague ON y encienda STANDBY
        sb_ctx = self.box_sb.get_style_context()
        sb_ctx.remove_class("state-box")
        sb_ctx.add_class("state-box-off")

    def update_state(self, off_active: bool): #Actualizar estados de los "LEDs" de la interfaz
        off_ctx = self.box_off.get_style_context()
        on_ctx = self.box_on.get_style_context()
        sb_ctx = self.box_sb.get_style_context()

        # Apaga ON/OFF
        off_ctx.remove_class("state-box-off")
        on_ctx.remove_class("state-box-on")

        # Apaga STANDBY
        sb_ctx.remove_class("state-box-off")
        sb_ctx.add_class("state-box")

        if off_active:
            off_ctx.add_class("state-box-off")
        else:
            on_ctx.add_class("state-box-on")

    def update_boxes(self): #actualizar la cantidad de cajas en la interfaz
        global cajas_cafe, cajas_banano, cajas_medico
        self.entries[0].set_text(str(cajas_banano))
        self.entries[1].set_text(str(cajas_cafe))
        self.entries[2].set_text(str(cajas_medico))

    def on_destroy(self, *_): #al cerra la ventana de la interfaz, destruya la interfaz y ponga en bajo el pin digital
        try:
            self.ser.close()
        except:
            pass
        self.pi.write(STOP_PIN, 0)
        self.pi.stop()
        Gtk.main_quit()
        
    def apply_css(self): #esto son estilos personalizados para el formato de botones, cuadros y texto
        css = b"""
        frame.state-box-off { background: #e67e22; }
        frame.state-box { background: #ffffff; }
        frame.state-box-on { background: #2ecc71; }
        label.big-label { font-size:20px; font-weight:bold; }
        entry.big-entry { font-size:18px; padding:8px; border:2px solid #2980b9; border-radius:5px; }
        button.start  { background-color:#2ecc71; color:white; font-size:22px; padding:20px 40px; border-radius:5px; }
        button.stop   { background-color:#e74c3c; color:white; font-size:22px; padding:20px 40px; border-radius:5px; }
        button.report { background-color:#95a5a6; color:white; font-size:18px; padding:15px 30px; border-radius:5px; }
        frame { border:2px solid #bdc3c7; border-radius:5px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

#Corra todo el codigo, genere la ventana
if __name__ == "__main__":
    ControlWindow()
    Gtk.main()