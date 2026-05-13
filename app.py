import streamlit as st
import pandas as pd
from io import BytesIO
import requests
from datetime import datetime

st.set_page_config(page_title="CALCULADORA INTERFACE A KILOS 1.0", page_icon="🍺", layout="wide")

st.title("🍺 CALCULADORA INTERFACE A KILOS 1.0")
st.markdown("Subí el archivo TXT con los datos de los remitos y obtené el peso total por remito")

# ============================================================
# URL DEL EXCEL EN GITHUB
# ============================================================
URL_EXCEL_GITHUB = "https://raw.githubusercontent.com/abulian14/calculadora-kilos/main/PESO%20X%20ARTICULOO.xlsx"

# ============================================================
# CARGAR EXCEL DESDE GITHUB
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
            return {}, f"❌ No se encontraron columnas 'CODIGO' y 'PESO'"
        df[col_codigo] = pd.to_numeric(df[col_codigo], errors='coerce')
        df[col_peso] = pd.to_numeric(df[col_peso], errors='coerce')
        df = df.dropna(subset=[col_codigo, col_peso])
        pesos = dict(zip(df[col_codigo].astype(int), df[col_peso]))
        return pesos, f"✅ Cargados {len(pesos)} productos desde GitHub"
    except Exception as e:
        return {}, f"❌ Error al cargar Excel: {str(e)}"

# ============================================================
# DECODIFICAR ARCHIVO
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
# PROCESAR TXT - USANDO COLUMNAS FIJAS (29 y 35)
# ============================================================
def procesar_txt(contenido, pesos_dict):
    lineas = contenido.strip().split('\n')
    productos = []
    codigos_validos = set(pesos_dict.keys())
    
    for num_linea, linea in enumerate(lineas, 1):
        linea = linea.strip()
        if not linea or 'ORIGEN' in linea:
            continue
        
        campos = linea.split(';')
        
        # Necesitamos al menos 35 columnas
        if len(campos) < 35:
            continue
        
        # Extraer por índice fijo (0-indexado)
        nro_remito = campos[1].strip()      # columna 2
        fecha_raw = campos[2].strip()       # columna 3
        cliente = campos[7].strip()         # columna 8
        codigo_str = campos[28].strip()     # columna 29
        cantidad_str = campos[34].strip()   # columna 35
        
        # Validar código
        if not codigo_str.isdigit() or len(codigo_str) != 7:
            continue
        
        codigo = int(codigo_str)
        if codigo not in codigos_validos:
            continue
        
        # Validar cantidad
        if not cantidad_str or not cantidad_str.replace('.', '').isdigit():
            continue
        
        cantidad = float(cantidad_str)
        if cantidad == 0:
            continue
        
        # Formatear fecha
        if len(fecha_raw) == 8 and fecha_raw.isdigit():
            fecha = f"{fecha_raw[6:8]}/{fecha_raw[4:6]}/{fecha_raw[0:4]}"
        else:
            fecha = fecha_raw
        
        productos.append({
            'remito': nro_remito,
            'fecha': fecha,
            'cliente': cliente,
            'codigo': codigo,
            'cantidad': cantidad
        })
    
    if not productos:
        return None, "No se encontraron productos válidos", pd.DataFrame()
    
    df = pd.DataFrame(productos)
    df['peso_unitario'] = df['codigo'].map(pesos_dict).fillna(0)
    df['peso_total_item'] = df['cantidad'] * df['peso_unitario']
    
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
    
    return resumen, [], df

# ============================================================
# GENERAR NOMBRE DE ARCHIVO
# ============================================================
def generar_nombre_reporte():
    ahora = datetime.now()
    return f"reporte_remitos ({ahora.strftime('%Y%m%d%H%M')}).xlsx"

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================
st.sidebar.header("📊 Base de Datos de Pesos")

with st.spinner("Cargando base de datos desde GitHub..."):
    pesos_dict, mensaje = cargar_pesos_desde_github()

st.sidebar.success(mensaje)
st.sidebar.info(f"📌 {len(pesos_dict)} productos disponibles")

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
        st.dataframe(resultado, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Remitos", len(resultado))
        col2.metric("Total Bultos", int(resultado['Total Bultos'].sum()))
        col3.metric("Peso Total", f"{resultado['Peso Total (kg)'].sum():.2f} kg")
        
        with st.expander("🔍 Ver detalle de productos detectados"):
            st.dataframe(detalle_productos[['remito', 'codigo', 'cantidad', 'peso_unitario', 'peso_total_item']])
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            resultado.to_excel(writer, sheet_name='Resumen por Remito', index=False)
            detalle_export = detalle_productos[['remito', 'codigo', 'cantidad', 'peso_unitario', 'peso_total_item']].copy()
            detalle_export.columns = ['N° Remito', 'Código Artículo', 'Cantidad Bultos', 'Peso Unitario (kg)', 'Subtotal (kg)']
            detalle_export.to_excel(writer, sheet_name='Detalle por Artículo', index=False)
            stats_data = [
                {'Indicador': 'Total Remitos', 'Valor': len(resultado)},
                {'Indicador': 'Total Bultos', 'Valor': int(resultado['Total Bultos'].sum())},
                {'Indicador': 'Peso Total General (kg)', 'Valor': round(resultado['Peso Total (kg)'].sum(), 2)},
                {'Indicador': 'Códigos procesados', 'Valor': len(detalle_productos)},
                {'Indicador': 'Fecha de procesamiento', 'Valor': datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            ]
            df_stats = pd.DataFrame(stats_data)
            df_stats.to_excel(writer, sheet_name='Estadísticas', index=False)
        
        st.download_button(
            label="📥 Descargar Reporte Excel",
            data=output.getvalue(),
            file_name=generar_nombre_reporte(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ No se encontraron datos válidos en el archivo")
