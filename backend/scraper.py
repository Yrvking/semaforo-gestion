import time
import os
import glob
import shutil
import logging
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Credenciales - Primero intenta variables de entorno, luego archivo local
def get_credentials():
    # Prioridad 1: Variables de entorno (para producción)
    user = os.getenv("EVOLTA_USERNAME")
    password = os.getenv("EVOLTA_PASSWORD")
    
    if user and password:
        logger.info("Using credentials from environment variables")
        return user, password
    
    # Prioridad 2: Archivo local (para desarrollo)
    local_paths = [
        os.path.join(os.path.dirname(__file__), "..", "CREDENCIALES.txt"),
        "c:\\Users\\Yrving\\SEMAFORO\\CREDENCIALES.txt",
        "/app/CREDENCIALES.txt"
    ]
    
    for path in local_paths:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    lines = f.readlines()
                    user = lines[0].split(":")[1].strip()
                    password = lines[1].split(":")[1].strip()
                    logger.info(f"Using credentials from file: {path}")
                    return user, password
        except Exception as e:
            logger.warning(f"Could not read credentials from {path}: {e}")
    
    # Fallback
    logger.warning("Using default credentials")
    return "Marketing", "Padovamarketing"

USER_CRED, PASS_CRED = get_credentials()

# Configuración - Directorio de descarga dinámico
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", r"C:\Users\Yrving\Downloads\CARPETA_SEMAFORO")
URL_LOGIN = "https://v4.evolta.pe/Login/Acceso/Index"

# URLs de Reportes
REPORTS = {
    "reporteProspectos": "https://v4.evolta.pe/Reportes/RepHiloProspectos/IndexProspecto",
    "ReporteVenta": "https://v4.evolta.pe/Reportes/RepVenta/Index",
    "Separacion": "https://v4.evolta.pe/Reportes/RepSeparacion/Index",
    "ReporteVisitas": "https://v4.evolta.pe/Reportes/RepVisita/IndexVisita"
}


class EvoltaScraper:
    def __init__(self, download_dir=DOWNLOAD_DIR):
        self.download_dir = download_dir
        self.driver = None
        self._ensure_download_dir()

    def _ensure_download_dir(self):
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        logger.info(f"Download Directory: {os.path.abspath(self.download_dir)}")

    def _get_existing_files(self):
        """Obtiene set de archivos actuales en el directorio"""
        files = glob.glob(os.path.join(self.download_dir, "*"))
        return set(f for f in files if not f.endswith('.crdownload') and not f.endswith('.tmp'))

    def start_driver(self):
        logger.info("Starting Chrome driver...")
        options = webdriver.ChromeOptions()
        
        # Detectar si estamos en Docker/producción
        is_production = os.getenv("ENVIRONMENT") == "production"
        
        if is_production:
            options.add_argument("--headless")
            options.add_argument("--disable-dev-shm-usage")
            chrome_bin = os.getenv("CHROME_BIN", "/usr/bin/google-chrome")
            options.binary_location = chrome_bin
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1920,1080")
        
        prefs = {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        options.add_experimental_option("prefs", prefs)
        
        # En producción usar chromedriver instalado, en desarrollo usar webdriver-manager
        if is_production:
            chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
            
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 30)
        logger.info("Chrome driver started")

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Driver closed")

    def login(self):
        logger.info("Logging in to Evolta...")
        try:
            self.driver.get(URL_LOGIN)
            time.sleep(2)
            
            # Buscar campo usuario
            user_field = None
            for selector in [
                (By.ID, "UserName"),
                (By.NAME, "Usuario"),
                (By.XPATH, "//input[@type='text']")
            ]:
                try:
                    user_field = self.driver.find_element(*selector)
                    break
                except:
                    continue
            
            if not user_field:
                raise Exception("No se encontró campo de usuario")
            
            user_field.clear()
            user_field.send_keys(USER_CRED)
            
            # Password
            pass_field = self.driver.find_element(By.XPATH, "//input[@type='password']")
            pass_field.send_keys(PASS_CRED)
            
            # Submit
            try:
                btn = self.driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
                btn.click()
            except:
                pass_field.send_keys(Keys.ENTER)
            
            # Esperar cambio de URL
            time.sleep(3)
            self._dismiss_popup()
            
            if "Login" not in self.driver.current_url:
                logger.info(f"Login exitoso: {self.driver.current_url}")
            else:
                raise Exception("Login fallido - URL no cambió")
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self._save_screenshot("error_login")
            raise

    def _dismiss_popup(self):
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except:
            pass

    def _save_screenshot(self, name):
        try:
            path = os.path.join(self.download_dir, f"{name}_{datetime.now().strftime('%H%M%S')}.png")
            self.driver.save_screenshot(path)
            logger.info(f"Screenshot: {path}")
        except:
            pass

    def _set_dates(self):
        """Configura fechas: inicio = 1ro del mes, fin = ayer"""
        now = datetime.now()
        first_day = now.replace(day=1).strftime("%d/%m/%Y")
        yesterday = (now - timedelta(days=1)).strftime("%d/%m/%Y")
        
        logger.info(f"Setting dates: {first_day} - {yesterday}")
        
        # Usar JavaScript para setear fechas
        script = f"""
            var inputs = document.querySelectorAll('input');
            var dateInputs = [];
            for (var i = 0; i < inputs.length; i++) {{
                var val = inputs[i].value || '';
                var placeholder = inputs[i].placeholder || '';
                if (val.match(/\\d{{2}}\\/\\d{{2}}\\/\\d{{4}}/) || placeholder.includes('fecha') || inputs[i].type === 'date') {{
                    dateInputs.push(inputs[i]);
                }}
            }}
            if (dateInputs.length >= 2) {{
                dateInputs[0].value = '{first_day}';
                dateInputs[1].value = '{yesterday}';
                dateInputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                dateInputs[1].dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        """
        result = self.driver.execute_script(script)
        time.sleep(1)
        return result

    def _wait_for_new_file(self, files_before, timeout=120):
        """Espera que aparezca un archivo NUEVO que no existía antes"""
        logger.info("Waiting for new file...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Verificar si hay archivos descargándose
            downloading = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
            if downloading:
                logger.info(f"Download in progress: {downloading}")
            
            # Obtener archivos actuales
            current_files = self._get_existing_files()
            
            # Encontrar archivos nuevos
            new_files = current_files - files_before
            
            if new_files:
                # Esperar un momento para asegurar que la descarga termine
                time.sleep(2)
                # Verificar de nuevo
                current_files = self._get_existing_files()
                new_files = current_files - files_before
                
                if new_files:
                    new_file = list(new_files)[0]
                    logger.info(f"New file detected: {new_file}")
                    return new_file
            
            time.sleep(1)
        
        logger.warning("Timeout waiting for new file")
        return None

    def _export_report(self, url, filename):
        """Exporta un reporte de la URL dada"""
        logger.info(f"=== Exporting: {filename} from {url} ===")
        
        # Guardar lista de archivos ANTES de descargar
        files_before = self._get_existing_files()
        logger.info(f"Files before download: {len(files_before)}")
        
        try:
            self.driver.get(url)
            time.sleep(3)
            self._dismiss_popup()
            
            # Zoom out para ver todo
            self.driver.execute_script("document.body.style.zoom='70%'")
            time.sleep(1)
            
            # Seleccionar todos los proyectos
            try:
                select_elements = self.driver.find_elements(By.TAG_NAME, "select")
                if select_elements:
                    select = Select(select_elements[0])
                    select.select_by_index(0)  # "Todos"
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"Select project warning: {e}")
            
            # Configurar fechas
            self._set_dates()
            time.sleep(1)
            
            # Scroll al fondo
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Click en Exportar
            export_clicked = False
            
            # Intentar por ID
            try:
                btn = self.wait.until(EC.element_to_be_clickable((By.ID, "btnExportar")))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", btn)
                export_clicked = True
                logger.info("Clicked btnExportar by ID")
            except:
                pass
            
            # Intentar por texto
            if not export_clicked:
                for xpath in [
                    "//button[contains(text(),'Exportar')]",
                    "//button[contains(text(),'EXPORTAR')]",
                    "//input[@value='Exportar']",
                    "//a[contains(text(),'Exportar')]"
                ]:
                    try:
                        btn = self.driver.find_element(By.XPATH, xpath)
                        self.driver.execute_script("arguments[0].click();", btn)
                        export_clicked = True
                        logger.info(f"Clicked export via: {xpath}")
                        break
                    except:
                        continue
            
            if not export_clicked:
                self._save_screenshot(f"error_export_{filename}")
                raise Exception(f"No se pudo clickear Exportar en {url}")
            
            # Esperar que aparezca archivo NUEVO
            new_file = self._wait_for_new_file(files_before)
            
            if new_file:
                # Renombrar al nombre deseado
                ext = os.path.splitext(new_file)[1]
                target = os.path.join(self.download_dir, f"{filename}{ext}")
                
                # Si el archivo nuevo YA tiene el nombre correcto, no hacer nada
                if os.path.abspath(new_file) == os.path.abspath(target):
                    logger.info(f"File already has correct name: {target}")
                    return target
                
                # Si ya existe el target, eliminarlo primero
                if os.path.exists(target):
                    try:
                        os.remove(target)
                        logger.info(f"Removed existing: {target}")
                    except Exception as e:
                        logger.warning(f"Could not remove {target}: {e}")
                        # Usar nombre alternativo
                        target = os.path.join(self.download_dir, f"{filename}_{datetime.now().strftime('%H%M%S')}{ext}")
                
                # Esperar un momento para asegurar que el archivo no está en uso
                time.sleep(1)
                
                # Renombrar
                try:
                    shutil.move(new_file, target)
                    logger.info(f"Saved as: {target}")
                    return target
                except Exception as e:
                    logger.warning(f"Could not move file: {e}")
                    # El archivo descargado sigue existiendo con su nombre original
                    logger.info(f"Keeping original: {new_file}")
                    return new_file
            else:
                logger.error(f"Download failed for {filename}")
                self._save_screenshot(f"error_download_{filename}")
                return None
                
        except Exception as e:
            logger.error(f"Export error for {filename}: {e}")
            self._save_screenshot(f"error_{filename}")
            return None

    def run_sync(self):
        """Ejecuta la sincronización completa"""
        logger.info("========== STARTING SYNC ==========")
        downloaded = []
        
        try:
            self.start_driver()
            self.login()
            
            for filename, url in REPORTS.items():
                logger.info(f"\n--- Processing: {filename} ---")
                result = self._export_report(url, filename)
                if result:
                    downloaded.append(result)
                    logger.info(f"SUCCESS: {filename}")
                else:
                    logger.error(f"FAILED: {filename}")
                time.sleep(3)  # Pausa entre descargas
            
            logger.info(f"\n========== SYNC COMPLETE ==========")
            logger.info(f"Downloaded {len(downloaded)}/{len(REPORTS)} files:")
            for f in downloaded:
                logger.info(f"  - {f}")
            
            return downloaded
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise
        finally:
            self.close()


if __name__ == "__main__":
    scraper = EvoltaScraper()
    scraper.run_sync()
