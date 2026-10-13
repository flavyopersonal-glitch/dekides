from pathlib import Path
import base64

import streamlit as st


@st.cache_data
def _logo_base64():
    return base64.b64encode((Path(__file__).parent / "assets" / "averlum-logo.png").read_bytes()).decode("ascii")


def mostrar_assinatura():
    st.sidebar.markdown(
        '<div style="margin:1rem 0">'
        '<div style="font-size:0.75rem;opacity:0.7;margin-bottom:0.4rem">Desenvolvido por</div>'
        f'<img src="data:image/png;base64,{_logo_base64()}" alt="Averlum" '
        'width="120" style="max-width:100%;height:auto;border-radius:6px">'
        '</div>',
        unsafe_allow_html=True,
    )
