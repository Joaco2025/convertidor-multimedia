import customtkinter as ctk
import yt_dlp
import os
import sys
import threading

# Configuración inicial
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def get_internal_path(filename):
    """
    Función mágica: 
    - Si es .exe: busca el archivo en la carpeta temporal interna.
    - Si es script: busca el archivo en la carpeta actual.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

class YoutubeAudioDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YT Music Downloader (Chito version) | Portable")
        self.geometry("600x420")
        self.resizable(False, False)

        # Ubicación local de ffmpeg (sea dentro del exe o fuera)
        self.ffmpeg_exe = get_internal_path("ffmpeg.exe")
        self.download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        
        self.create_widgets()

    def create_widgets(self):
        # Header
        self.title_label = ctk.CTkLabel(self, text="YouTube a MP3 Converter", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=20)

        # Verificación de Motor (Solo visual)
        if os.path.exists(self.ffmpeg_exe):
            status_text = "Motor de Audio: INTEGRADO (Listo para MP3)"
            color = "#4ade80" # Verde
        else:
            status_text = "ADVERTENCIA: No se encuentran los archivos de audio"
            color = "red"
            
        self.ffmpeg_label = ctk.CTkLabel(self, text=status_text, text_color=color, font=("Roboto", 12))
        self.ffmpeg_label.pack(pady=(0, 10))

        # Input
        self.url_entry = ctk.CTkEntry(self, width=450, placeholder_text="Pega el enlace de YouTube aquí...")
        self.url_entry.pack(pady=10)

        # Botón
        self.download_btn = ctk.CTkButton(self, text="DESCARGAR MP3", command=self.start_download_thread, height=40, font=("Roboto", 14, "bold"))
        self.download_btn.pack(pady=20)

        # Progreso
        self.progress_bar = ctk.CTkProgressBar(self, width=450)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)
        
        self.percentage_label = ctk.CTkLabel(self, text="0%")
        self.percentage_label.pack()

        # Estado
        self.status_label = ctk.CTkLabel(self, text="Listo", text_color="gray")
        self.status_label.pack(pady=10)

    def start_download_thread(self):
        url = self.url_entry.get()
        if not url:
            self.status_label.configure(text="Error: Ingresa una URL", text_color="red")
            return

        self.download_btn.configure(state="disabled")
        self.status_label.configure(text="Iniciando...", text_color="white")
        
        thread = threading.Thread(target=self.download_logic, args=(url,))
        thread.start()

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                p = d.get('_percent_str', '0%').replace('%', '')
                self.progress_bar.set(float(p) / 100)
                self.percentage_label.configure(text=d.get('_percent_str', '0%'))
                self.status_label.configure(text="Descargando...")
            except: pass
        elif d['status'] == 'finished':
            self.progress_bar.set(1)
            self.percentage_label.configure(text="100%")
            self.status_label.configure(text="Convirtiendo a MP3... (Espere)", text_color="orange")

    def download_logic(self, url):
        try:
            # Importante: Le decimos a yt-dlp dónde está la carpeta con los .exe
            ffmpeg_location_dir = os.path.dirname(self.ffmpeg_exe)

            ydl_opts = {
                'outtmpl': f'{self.download_folder}/%(title)s.%(ext)s',
                'progress_hooks': [self.progress_hook],
                'noplaylist': True,
                'format': 'bestaudio/best',
                'ffmpeg_location': ffmpeg_location_dir, # <-- Aquí está la clave
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            self.status_label.configure(text=f"¡Éxito! MP3 guardado en Descargas", text_color="#4ade80")

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)[:50]}...", text_color="red")
            print(e)
        
        finally:
            self.download_btn.configure(state="normal")

if __name__ == "__main__":
    app = YoutubeAudioDownloader()
    app.mainloop()