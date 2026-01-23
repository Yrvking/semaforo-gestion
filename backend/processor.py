import os
import glob
import pandas as pd
import json
import logging
import math
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

META_FILE = "meta_data.json"

TARGET_PROJECTS = [
    'HELIO - SANTA BEATRIZ',
    'LITORAL 900', 
    'LOMAS DE CARABAYLLO',
    'SUNNY'
]

# Estructura de metas por defecto (igual que en Excel META)
DEFAULT_META = {
    "prospectos_totales": 0,      # Leads Totales
    "prospectos_digitales": 0,    # Leads Digitales (se calcula como prospectos_totales - 5%)
    "contactados": 0,             # Prospectos/Contactados (se calcula como 25% de leads)
    "visitas_sala": 0,            # Visitas Totales
    "separaciones_totales": 0,    # Separaciones
    "metas_minutas": 0            # Ventas
}


class SemaforoProcessor:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.data = {}
        self.meta = self._load_meta()

    def _load_meta(self):
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_meta(self, new_meta):
        self.meta = new_meta
        with open(META_FILE, 'w') as f:
            json.dump(self.meta, f, indent=2)

    def _get_latest_file(self, prefix):
        """Busca el archivo más reciente con el prefijo dado"""
        for ext in ['.xlsx', '.xls', '.csv']:
            pattern = os.path.join(self.download_dir, f"{prefix}*{ext}")
            files = glob.glob(pattern)
            if files:
                return max(files, key=os.path.getctime)
        
        logger.warning(f"No file found for prefix: {prefix}")
        return None

    def _load_file(self, filepath):
        """Carga un archivo Excel o CSV"""
        if not filepath:
            return pd.DataFrame()
        
        try:
            if filepath.endswith('.csv'):
                return pd.read_csv(filepath)
            else:
                return pd.read_excel(filepath, engine='openpyxl')
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return pd.DataFrame()

    def load_data(self):
        """Carga todos los archivos de datos"""
        files_config = {
            'prospectos': 'reporteProspectos',
            'ventas': 'ReporteVenta',
            'separaciones': 'Separacion',
            'visitas': 'ReporteVisitas'
        }
        
        for key, prefix in files_config.items():
            filepath = self._get_latest_file(prefix)
            if filepath:
                df = self._load_file(filepath)
                if not df.empty:
                    df.columns = df.columns.str.strip()
                    self.data[key] = df
                    logger.info(f"Loaded {len(df)} rows for {key}")

    def _get_meta_al_dia(self):
        """Calcula el porcentaje del mes transcurrido (C11 en Excel)"""
        now = datetime.now()
        dias_mes = (datetime(now.year, now.month + 1, 1) - datetime(now.year, now.month, 1)).days if now.month < 12 else 31
        dia_actual = now.day
        return dia_actual / dias_mes

    def _count_leads_totales(self, df, project):
        """
        ContarLeadTotales.bas:
        Cuenta donde Proyecto = project AND LeadUnicoxMesProyecto = "SI"
        """
        if df.empty:
            return 0
        
        # Buscar columnas (pueden variar de posición)
        project_col = None
        lead_unico_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO':
                project_col = col
            elif col_upper == 'LEADUNICOXMESPROYECTO':
                lead_unico_col = col
        
        if project_col is None or lead_unico_col is None:
            logger.warning(f"Columnas no encontradas para LEADS TOTALES: Proyecto={project_col}, LeadUnicoxMesProyecto={lead_unico_col}")
            return 0
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[lead_unico_col].astype(str).str.upper().str.strip() == 'SI')
        )
        return int(mask.sum())

    def _count_leads_digitales(self, df, project):
        """
        ContarLead_digital.bas:
        Cuenta donde Proyecto = project AND LeadUnicoxMesProyecto = "SI" 
        AND ComoSeEntero contiene fuentes digitales
        """
        if df.empty:
            return 0
        
        project_col = None
        lead_unico_col = None
        como_se_entero_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO':
                project_col = col
            elif col_upper == 'LEADUNICOXMESPROYECTO':
                lead_unico_col = col
            elif col_upper == 'COMOSEENTERO':
                como_se_entero_col = col
        
        if project_col is None or lead_unico_col is None or como_se_entero_col is None:
            logger.warning(f"Columnas no encontradas para LEADS DIGITALES")
            return 0
        
        # Fuentes digitales según Excel de Santa Beatriz
        # Busca palabras clave que identifiquen canales digitales
        digital_keywords = [
            'META',           # META ADS
            'FACEBOOK',       # Facebook Ads
            'NEXO',           # NEXO INMOBILIARIO, FERIA NEXO INMOBILIARIO
            'WHATSAPP',       # WHATSAPP, WHATSAPP FERIA
            'PAGINA WEB',     # PAGINA WEB
            'WEB',            # Variaciones de web
            'TIK TOK',        # TIK TOK ADS
            'TIKTOK',         # Variación sin espacio
            'FERIA',          # FERIA NEXO INMOBILIARIO, WHATSAPP FERIA
            'ADS',            # META ADS, TIK TOK ADS
            'DIGITAL',        # Cualquier fuente digital
            'INSTAGRAM',      # Instagram
            'GOOGLE',         # Google Ads
        ]
        
        # Crear patrón regex para buscar cualquiera de las palabras clave
        pattern = '|'.join(digital_keywords)
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[lead_unico_col].astype(str).str.upper().str.strip() == 'SI') &
            (df[como_se_entero_col].astype(str).str.upper().str.contains(pattern, na=False, regex=True))
        )
        return int(mask.sum())

    def _count_leads_con_dni(self, df, project):
        """
        Cuenta leads únicos con DNI:
        Proyecto = project AND LeadUnicoxMesProyecto = "SI" AND NroDocumento tiene valor
        """
        if df.empty:
            return 0
        
        project_col = None
        lead_unico_col = None
        nro_doc_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO':
                project_col = col
            elif col_upper == 'LEADUNICOXMESPROYECTO':
                lead_unico_col = col
            elif col_upper == 'NRODOCUMENTO':
                nro_doc_col = col
        
        if project_col is None or lead_unico_col is None:
            return 0
        
        # Si no hay columna de DNI, contar solo leads únicos
        if nro_doc_col is None:
            mask = (
                (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
                (df[lead_unico_col].astype(str).str.upper().str.strip() == 'SI')
            )
        else:
            mask = (
                (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
                (df[lead_unico_col].astype(str).str.upper().str.strip() == 'SI') &
                (df[nro_doc_col].notna()) &
                (df[nro_doc_col].astype(str).str.strip() != '')
            )
        return int(mask.sum())

    def _count_prospectos_contactados(self, df, project):
        """
        Cuenta prospectos contactados:
        Proyecto = project AND LeadUnicoxMesProyecto = "SI" AND SubEstado = "CONTACTADO"
        """
        if df.empty:
            return 0
        
        project_col = None
        lead_unico_col = None
        subestado_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO':
                project_col = col
            elif col_upper == 'LEADUNICOXMESPROYECTO':
                lead_unico_col = col
            elif col_upper == 'SUBESTADO':
                subestado_col = col
        
        if project_col is None or lead_unico_col is None or subestado_col is None:
            logger.warning(f"Columnas no encontradas para PROSPECTOS CONTACTADOS")
            return 0
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[lead_unico_col].astype(str).str.upper().str.strip() == 'SI') &
            (df[subestado_col].astype(str).str.upper().str.strip() == 'CONTACTADO')
        )
        return int(mask.sum())

    def _count_separaciones(self, df, project):
        """
        ContarSeparaciones.bas:
        Cuenta donde DescripcionProyecto = project AND TipoInmueble_1 = "Departamento"
        """
        if df.empty:
            return 0
        
        project_col = None
        tipo_inmueble_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'DESCRIPCIONPROYECTO':
                project_col = col
            elif col_upper == 'TIPOINMUEBLE_1':
                tipo_inmueble_col = col
        
        if project_col is None or tipo_inmueble_col is None:
            logger.warning(f"Columnas no encontradas para SEPARACIONES")
            return 0
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[tipo_inmueble_col].astype(str).str.upper().str.strip() == 'DEPARTAMENTO')
        )
        return int(mask.sum())

    def _count_ventas(self, df, project):
        """
        ContarVentas.bas:
        Cuenta donde Proyecto = project AND TipoInmueble_1 = "Departamento"
        """
        if df.empty:
            return 0
        
        project_col = None
        tipo_inmueble_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO':
                project_col = col
            elif col_upper == 'TIPOINMUEBLE_1':
                tipo_inmueble_col = col
        
        if project_col is None or tipo_inmueble_col is None:
            logger.warning(f"Columnas no encontradas para VENTAS")
            return 0
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[tipo_inmueble_col].astype(str).str.upper().str.strip() == 'DEPARTAMENTO')
        )
        return int(mask.sum())

    def _count_proformas(self, df, project):
        """
        ContarProformas.bas:
        Cuenta donde DescripcionProyecto = project AND FlgUnicoMesProy = "SI"
        Hoja: ReporteProforma
        """
        if df.empty:
            return 0
        
        project_col = None
        flg_unico_col = None
        
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'DESCRIPCIONPROYECTO':
                project_col = col
            elif col_upper == 'FLGUNICOMESPROJ' or col_upper == 'FLGUNICOMESPROYECTO':
                flg_unico_col = col
        
        if project_col is None or flg_unico_col is None:
            logger.warning(f"Columnas no encontradas para PROFORMAS")
            return 0
        
        mask = (
            (df[project_col].astype(str).str.upper().str.strip() == project.upper()) &
            (df[flg_unico_col].astype(str).str.upper().str.strip() == 'SI')
        )
        return int(mask.sum())

    def _count_visitas(self, df, project):
        """
        Cuenta visitas por proyecto
        """
        if df.empty:
            return 0
        
        project_col = None
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == 'PROYECTO' or col_upper == 'DESCRIPCIONPROYECTO':
                project_col = col
                break
        
        if project_col is None:
            logger.warning(f"Columna de proyecto no encontrada para VISITAS")
            return 0
        
        mask = df[project_col].astype(str).str.upper().str.strip() == project.upper()
        return int(mask.sum())

    def calculate_metrics(self):
        """Calcula métricas para cada proyecto siguiendo las fórmulas del Excel VBA"""
        metrics = []
        
        df_p = self.data.get('prospectos', pd.DataFrame())
        df_v = self.data.get('ventas', pd.DataFrame())
        df_s = self.data.get('separaciones', pd.DataFrame())
        df_vis = self.data.get('visitas', pd.DataFrame())
        
        meta_al_dia = self._get_meta_al_dia()
        logger.info(f"Meta al día: {meta_al_dia:.2%}")
        
        # Log columnas disponibles para debug
        if not df_p.empty:
            logger.info(f"Columnas en prospectos: {list(df_p.columns)}")
        
        for project in TARGET_PROJECTS:
            # Inicializar meta si no existe
            if project not in self.meta:
                self.meta[project] = DEFAULT_META.copy()
            
            project_meta = self.meta[project]
            row = {"Proyecto": project, "Metrics": {}}
            
            # ============ LEADS TOTALES ============
            # VBA: ContarLeadTotales.bas
            # REAL = CONTAR.SI.CONJUNTO(Proyecto; project; LeadUnicoxMesProyecto; "SI")
            meta_leads = project_meta.get("prospectos_totales", 0)
            meta_leads_dia = math.ceil(meta_leads * meta_al_dia) if meta_leads > 0 else 0
            real_leads = self._count_leads_totales(df_p, project)
            pct_leads = round((real_leads / meta_leads_dia * 100), 0) if meta_leads_dia > 0 else 0
            
            row["Metrics"]["Leads Totales"] = {
                "Meta": meta_leads,
                "MetaDia": meta_leads_dia,
                "Real": real_leads,
                "Pct": pct_leads
            }
            
            # ============ LEADS CON DNI ============
            # Cuenta leads donde LeadUnicoxMesProyecto = "SI" Y NroDocumento tiene valor
            real_dni = self._count_leads_con_dni(df_p, project)
            
            row["Metrics"]["Leads DNI"] = {
                "Real": real_dni
            }
            
            # ============ LEADS DIGITALES ============
            # VBA: ContarLead_digital.bas
            # REAL = Proyecto + LeadUnicoxMesProyecto="SI" + ComoSeEntero contiene (Facebook, Whatsapp, Pagina Web, Nexo)
            meta_digital = project_meta.get("prospectos_digitales", 0)
            meta_digital_dia = math.ceil(meta_digital * meta_al_dia) if meta_digital > 0 else 0
            real_digital = self._count_leads_digitales(df_p, project)
            pct_digital = round((real_digital / meta_digital_dia * 100), 0) if meta_digital_dia > 0 else 0
            
            row["Metrics"]["Leads Digitales"] = {
                "Meta": meta_digital,
                "MetaDia": meta_digital_dia,
                "Real": real_digital,
                "Pct": pct_digital
            }
            
            # ============ PROSPECTOS (Contactados) ============
            # Cuenta leads donde Proyecto + LeadUnicoxMesProyecto="SI" + SubEstado="CONTACTADO"
            meta_contactados = project_meta.get("contactados", 0)
            meta_contactados_dia = math.ceil(meta_contactados * meta_al_dia) if meta_contactados > 0 else 0
            real_contactados = self._count_prospectos_contactados(df_p, project)
            pct_contactados = round((real_contactados / meta_contactados_dia * 100), 0) if meta_contactados_dia > 0 else 0
            
            row["Metrics"]["Prospectos"] = {
                "Meta": meta_contactados,
                "MetaDia": meta_contactados_dia,
                "Real": real_contactados,
                "Pct": pct_contactados
            }
            
            # ============ VISITAS TOTALES ============
            meta_visitas = project_meta.get("visitas_sala", 0)
            meta_visitas_dia = math.ceil(meta_visitas * meta_al_dia) if meta_visitas > 0 else 0
            real_visitas = self._count_visitas(df_vis, project)
            pct_visitas = round((real_visitas / meta_visitas_dia * 100), 0) if meta_visitas_dia > 0 else 0
            
            row["Metrics"]["Visitas Totales"] = {
                "Meta": meta_visitas,
                "MetaDia": meta_visitas_dia,
                "Real": real_visitas,
                "Pct": pct_visitas
            }
            
            # ============ SEPARACIONES TOTALES ============
            # VBA: ContarSeparaciones.bas
            # REAL = DescripcionProyecto + TipoInmueble_1 = "Departamento"
            meta_sep = project_meta.get("separaciones_totales", 0)
            meta_sep_dia = math.ceil(meta_sep * meta_al_dia) if meta_sep > 0 else 0
            real_sep = self._count_separaciones(df_s, project)
            pct_sep = round((real_sep / meta_sep_dia * 100), 0) if meta_sep_dia > 0 else 0
            
            row["Metrics"]["Separaciones Totales"] = {
                "Meta": meta_sep,
                "MetaDia": meta_sep_dia,
                "Real": real_sep,
                "Pct": pct_sep
            }
            
            # ============ VENTAS TOTALES ============
            # VBA: ContarVentas.bas
            # REAL = Proyecto + TipoInmueble_1 = "Departamento"
            meta_ventas = project_meta.get("metas_minutas", 0)
            meta_ventas_dia = math.ceil(meta_ventas * meta_al_dia) if meta_ventas > 0 else 0
            real_ventas = self._count_ventas(df_v, project)
            pct_ventas = round((real_ventas / meta_ventas_dia * 100), 0) if meta_ventas_dia > 0 else 0
            
            row["Metrics"]["Ventas Totales"] = {
                "Meta": meta_ventas,
                "MetaDia": meta_ventas_dia,
                "Real": real_ventas,
                "Pct": pct_ventas
            }
            
            metrics.append(row)
            logger.info(f"{project}: Leads={real_leads}, Digitales={real_digital}, Prospectos={real_contactados}, Visitas={real_visitas}, Sep={real_sep}, Ventas={real_ventas}")
        
        return metrics

    def get_all_metas(self):
        """Retorna todas las metas para la UI de edición"""
        result = {}
        for project in TARGET_PROJECTS:
            if project not in self.meta:
                self.meta[project] = DEFAULT_META.copy()
            result[project] = self.meta[project]
        return result

    def update_project_meta(self, project, meta_key, value):
        """Actualiza una meta específica de un proyecto"""
        if project not in self.meta:
            self.meta[project] = DEFAULT_META.copy()
        
        self.meta[project][meta_key] = value
        self.save_meta(self.meta)
