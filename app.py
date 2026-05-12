import streamlit as st
import pandas as pd
from io import BytesIO
import re
import requests

st.set_page_config(page_title="CALCULADORA INTERFACE A KILOS 1.0", page_icon="🍺", layout="wide")

st.title("🍺 CALCULADORA INTERFACE A KILOS 1.0")
st.markdown("Subí el archivo TXT con los datos de los remitos y obtené el peso total por remito")

# ============================================================
# URL DEL EXCEL EN GITHUB (CONFIGURADA PARA abulian14)
# ============================================================
URL_EXCEL_GITHUB = "https://raw.githubusercontent.com/abulian14/calculadora-kilos/main/PESO%20X%20ARTICULOO.xlsx"

# ============================================================
# BASE DE DATOS DE PESOS POR DEFECTO (fallback)
# ============================================================
PESOS_POR_DEFECTO = {
    1130001: 13.3, 1130015: 12.7, 1130016: 12.7, 1130017: 12.7, 1130018: 12.7,
    1133015: 12.7, 8880113: 3.6, 8880518: 1.9, 1140001: 13.3, 1140002: 13.3,
    1140003: 13.3, 1140015: 12.7, 1150006: 14.4, 1150008: 14.4, 1150010: 14.4,
    1150016: 12.7, 1150017: 12.7, 1150018: 13.1, 1150019: 13.1, 8880115: 2.7,
    8880117: 3.6, 8880502: 3.1, 8880512: 2.3, 8880513: 1.9, 1150100: 31.5,
    1230041: 13.4, 1230042: 13.4, 1230043: 13.4, 1230044: 13.4, 1230141: 12.2,
    1230142: 12.2, 1230144: 12.2, 1230143: 12.2, 1230026: 12.6, 1230027: 12.6,
    1230016: 11.2, 1230017: 11.2, 1230018: 11.2, 8880105: 1.5, 8880106: 1.5,
}

# ============================================================
# FUNCIÓN PARA CARGAR EXCEL DESDE GITHUB
# ============================================================
@st.cache_data(ttl=3600)
def cargar_pesos_desde_github():
    try:
        response = requests.get(URL_EXCEL_GITHUB)
        response.raise_for_status()
        
        with open("temp_pesos.xlsx", "wb") as f:
            f.write(response.content)
        
        df = pd.read_excel("temp_pesos.xlsx", sheet_name='Hoja2')
        df = df.dropna(how='all')
        
        encabezado_fila = None
        for i, row in df.iterrows():
            if row.astype(str).str.contains('CODIGO', case=False, na=False).any():
                encabezado_fila = i
                break
        
        if encabezado_fila is not None:
            df = pd.read_excel("temp_pesos.xlsx", sheet_name='Hoja2', header=encabezado_fila)
        
        col_codigo = None
        col_peso = None
        
        for col in df.columns:
            col_str = str(col).upper().strip()
            if 'CODIGO' in col_str or 'COD' in col_str:
                col_codigo = col
            if 'PESO' in col_str or 'KG' in col_str:
                col_peso = col
        
        if col_codigo is None or col_peso is None:
            return PESOS_POR_DEFECTO, f"⚠️ Columnas no encontradas: {df.columns.tolist()}"
        
        df[col_codigo] = pd.to_numeric(df[col_codigo], errors='coerce')
        df[col_peso] = pd.to_numeric(df[col_peso], errors='coerce')
        df = df.dropna(subset=[col_codigo, col_peso])
        
        pesos = dict(zip(df[col_codigo].astype(int), df[col_peso]))
        return pesos, f"✅ Cargados {len(pesos)} productos desde GitHub"
        
    except Exception as e:
        return PESOS_POR_DEFECTO, f"⚠️ Usando pesos por defecto. Error: {str(e)}"

# ============================================================
# FUNCIÓN PARA DECODIFICAR ARCHIVO
# ============================================================
def decodificar_archivo(bytes_archivo):
    codificaciones = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    for encoding in codificaciones:
        try:
            texto = bytes_archivo.decode(encoding)
            return texto, encoding
        except UnicodeDecodeError:
            continue
    return bytes_archivo.decode('latin-1', errors='replace'), 'latin-1'

# ============================================================
# PROCESAR TXT - VERSIÓN CORREGIDA (detecta TODOS los códigos)
# ============================================================
def procesar_txt(contenido, pesos_dict):
    lineas = contenido.strip().split('\n')
    
    productos = []  # Lista para almacenar cada producto encontrado
    
    for num_linea, linea in enumerate(lineas, 1):
        linea = linea.strip()
        if not linea or 'ORIGEN' in linea:
            continue
        
        # Buscar código de 7 dígitos en TODA la línea
        codigo_match = re.search(r'\b(\d{7})\b', linea)
        if not codigo_match:
            continue
        codigo = int(codigo_match.group(1))
        
        # Buscar cantidad: patrón como 0000010.00, 0000005.00, 0000018.00
        cantidad_match = re.search(r'0{6}(\d+)\.(\d{2})', linea)
        if not cantidad_match:
            continue
        
        cantidad = float(f"{cantidad_match.group(1)}.{cantidad_match.group(2)}")
        
        # Extraer remito (está en el campo 2, separado por ;)
        campos = linea.split(';')
        if len(campos) > 1:
            nro_remito = campos[1].strip()
        else:
            nro_remito = "DESCONOCIDO"
        
        # Extraer fecha (campo 3)
        if len(campos) > 2:
            fecha_raw = campos[2].strip()
            if len(fecha_raw) == 8 and fecha_raw.isdigit():
                fecha = f"{fecha_raw[6:8]}/{fecha_raw[4:6]}/{fecha_raw[0:4]}"
            else:
                fecha = fecha_raw
        else:
            fecha = "S/F"
        
        # Extraer cliente (campo 8)
        if len(campos) > 7:
            cliente = campos[7].strip()
        else:
            cliente = "S/C"
        
        productos.append({
            'remito': nro_remito,
            'fecha': fecha,
            'cliente': cliente,
            'codigo': codigo,
            'cantidad': cantidad,
            'linea': num_linea
        })
    
    if not productos:
        return None, "No se encontraron datos válidos en el archivo"
    
    df = pd.DataFrame(productos)
    
    # Agregar pesos
    df['peso_unitario'] = df['codigo'].map(pesos_dict).fillna(0)
    df['peso_total_item'] = df['cantidad'] * df['peso_unitario']
    
    # Códigos sin peso
    sin_peso = df[df['peso_unitario'] == 0]['codigo'].unique().tolist()
    
    # Resumen por remito
    resumen = df.groupby('remito').agg({
        'cantidad': 'sum',
        'peso_total_item': 'sum',
        'fecha': 'first',
        'cliente': 'first'
    }).reset_index()
    
    resumen.columns = ['N° Remito', 'Total Bultos', 'Peso Total (kg)', 'Fecha', 'Cliente']
    resumen['Peso Total (kg)'] = resumen['Peso Total (kg)'].round(2)
    resumen = resumen[['Fecha', 'N° Remito', 'Cliente', 'Total Bultos', 'Peso Total (kg)']]
    
    return resumen, sin_peso, df

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================
st.sidebar.header("📊 Base de Datos de Pesos")

with st.spinner("Cargando base de datos desde GitHub..."):
    pesos_dict, mensaje = cargar_pesos_desde_github()

st.sidebar.success(mensaje)
st.sidebar.info(f"📌 {len(pesos_dict)} productos disponibles")

# Mostrar códigos disponibles
with st.sidebar.expander("📋 Ver códigos disponibles"):
    codigos_mostrar = sorted(list(pesos_dict.keys()))[:30]
    st.write(codigos_mostrar)
    if len(pesos_dict) > 30:
        st.caption(f"... y {len(pesos_dict) - 30} más")

st.header("📄 Procesar Remitos")
archivo_subido = st.file_uploader("Seleccioná el archivo TXT con los remitos", type=['txt'])

if archivo_subido is not None:
    archivo_bytes = archivo_subido.getvalue()
    contenido, encoding_usado = decodificar_archivo(archivo_bytes)
    
    st.info(f"📄 Codificación detectada: {encoding_usado}")
    
    with st.spinner("Procesando..."):
        resultado, sin_peso, detalle_productos = procesar_txt(contenido, pesos_dict)
    
    if resultado is not None and not resultado.empty:
        st.success(f"✅ Procesado! {len(resultado)} remitos encontrados")
        
        # Mostrar tabla de resultados
        st.subheader("📊 Resumen por Remito")
        st.dataframe(resultado, use_container_width=True)
        
        # Estadísticas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Remitos", len(resultado))
        col2.metric("Total Bultos", int(resultado['Total Bultos'].sum()))
        col3.metric("Peso Total", f"{resultado['Peso Total (kg)'].sum():.2f} kg")
        
        # Advertencias
        if sin_peso:
            st.warning(f"⚠️ Códigos sin peso en la base de datos: {sin_peso}")
        
        # Mostrar detalle de productos detectados (expandible)
        with st.expander("🔍 Ver detalle de productos detectados en el archivo"):
            st.dataframe(detalle_productos[['linea', 'remito', 'codigo', 'cantidad', 'peso_unitario', 'peso_total_item']], use_container_width=True)
        
        # ============================================================
        # GENERAR EXCEL CON MÚLTIPLES SOLAPAS
        # ============================================================
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Solapa 1: Resumen por Remito
            resultado.to_excel(writer, sheet_name='Resumen por Remito', index=False)
            
            # Solapa 2: Detalle de Interface
            detalle_export = detalle_productos[['remito', 'codigo', 'cantidad', 'peso_unitario', 'peso_total_item']].copy()
            detalle_export.columns = ['N° Remito', 'Código Artículo', 'Cantidad Bultos', 'Peso Unitario (kg)', 'Subtotal (kg)']
            detalle_export.to_excel(writer, sheet_name='Detalle por Artículo', index=False)
            
            # Solapa 3: Estadísticas
            stats_data = [
                {'Indicador': 'Total Remitos', 'Valor': len(resultado)},
                {'Indicador': 'Total Bultos', 'Valor': int(resultado['Total Bultos'].sum())},
                {'Indicador': 'Peso Total General (kg)', 'Valor': round(resultado['Peso Total (kg)'].sum(), 2)},
                {'Indicador': 'Códigos sin peso', 'Valor': len(sin_peso)},
                {'Indicador': 'Fecha de procesamiento', 'Valor': pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}
            ]
            df_stats = pd.DataFrame(stats_data)
            df_stats.to_excel(writer, sheet_name='Estadísticas', index=False)
        
        st.download_button(
            label="📥 Descargar Reporte Excel",
            data=output.getvalue(),
            file_name="reporte_remitos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    else:
        st.error(f"❌ {sin_peso if sin_peso else 'No se encontraron datos válidos en el archivo'}")
