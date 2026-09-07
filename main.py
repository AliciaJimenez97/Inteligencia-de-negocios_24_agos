import warnings

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
from statsbombpy import sb
from statsbombpy.api_client import NoAuthWarning


# Esta aplicación usa únicamente los datos abiertos de StatsBomb.
# La advertencia de falta de credenciales es normal en este caso.
warnings.filterwarnings("ignore", category=NoAuthWarning)

st.set_page_config(
    page_title="Análisis de partidos | StatsBomb",
    page_icon="⚽",
    layout="wide",
)


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_competiciones() -> pd.DataFrame:
    """Descarga la lista de competiciones abiertas y la guarda una hora."""
    return sb.competitions()


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_partidos(competition_id: int, season_id: int) -> pd.DataFrame:
    """Descarga los partidos de la competición y temporada elegidas."""
    return sb.matches(competition_id=competition_id, season_id=season_id)


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_eventos(match_id: int) -> pd.DataFrame:
    """Descarga todos los eventos del partido elegido."""
    return sb.events(match_id=match_id)


st.title("⚽ Explorador de datos de StatsBomb")
st.write(
    "Selecciona una competición, una temporada y un partido para consultar "
    "sus eventos, sus datos faltantes y sus pases."
)

try:
    with st.spinner("Cargando las competiciones disponibles..."):
        competitions = cargar_competiciones()
except Exception as error:
    st.error(f"No fue posible cargar las competiciones: {error}")
    st.stop()


# Primero se elige la competición.
competition_names = sorted(competitions["competition_name"].dropna().unique())
default_competition = (
    competition_names.index("FIFA World Cup")
    if "FIFA World Cup" in competition_names
    else 0
)

st.sidebar.header("Filtros")
competition_name = st.sidebar.selectbox(
    "Competición",
    competition_names,
    index=default_competition,
)

# Después se muestran únicamente las temporadas de esa competición.
competition_rows = competitions.loc[
    competitions["competition_name"] == competition_name
].copy()
competition_rows["season_label"] = (
    competition_rows["season_name"].astype(str)
    + " — "
    + competition_rows["country_name"].astype(str)
    + " (ID "
    + competition_rows["season_id"].astype(str)
    + ")"
)
competition_rows = competition_rows.sort_values("season_name", ascending=False)

season_label = st.sidebar.selectbox(
    "Temporada",
    competition_rows["season_label"].tolist(),
)
selected_competition = competition_rows.loc[
    competition_rows["season_label"] == season_label
].iloc[0]

competition_id = int(selected_competition["competition_id"])
season_id = int(selected_competition["season_id"])

try:
    with st.spinner("Cargando los partidos..."):
        matches = cargar_partidos(competition_id, season_id)
except Exception as error:
    st.error(f"No fue posible cargar los partidos: {error}")
    st.stop()

if matches.empty:
    st.warning("No se encontraron partidos para esta selección.")
    st.stop()


# El filtro de equipo permite reproducir el ejemplo de Japón, pero también
# explorar cualquier otro equipo disponible en la temporada.
teams = sorted(
    set(matches["home_team"].dropna()) | set(matches["away_team"].dropna())
)
team_options = ["Todos los equipos"] + teams
default_team = team_options.index("Japan") if "Japan" in team_options else 0
team = st.sidebar.selectbox("Equipo", team_options, index=default_team)

filtered_matches = matches.copy()
if team != "Todos los equipos":
    filtered_matches = filtered_matches.loc[
        (filtered_matches["home_team"] == team)
        | (filtered_matches["away_team"] == team)
    ]

if filtered_matches.empty:
    st.warning("No se encontraron partidos para el equipo seleccionado.")
    st.stop()


def etiqueta_partido(row: pd.Series) -> str:
    """Crea el texto que aparecerá en el selector de partidos."""
    return (
        f"{row['match_date']} | {row['home_team']} {row['home_score']}–"
        f"{row['away_score']} {row['away_team']} | ID {row['match_id']}"
    )


filtered_matches = filtered_matches.copy()
filtered_matches["match_label"] = filtered_matches.apply(etiqueta_partido, axis=1)
match_label = st.sidebar.selectbox(
    "Partido",
    filtered_matches["match_label"].tolist(),
)
selected_match = filtered_matches.loc[
    filtered_matches["match_label"] == match_label
].iloc[0]
match_id = int(selected_match["match_id"])

try:
    with st.spinner("Cargando los eventos del partido..."):
        events = cargar_eventos(match_id)
except Exception as error:
    st.error(f"No fue posible cargar los eventos: {error}")
    st.stop()


st.subheader(
    f"{selected_match['home_team']} {selected_match['home_score']}–"
    f"{selected_match['away_score']} {selected_match['away_team']}"
)

metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("ID del partido", match_id)
metric_2.metric("Eventos", f"{len(events):,}")
metric_3.metric("Variables", len(events.columns))

tab_matches, tab_events, tab_missing, tab_passes = st.tabs(
    ["Partidos", "Eventos", "Datos faltantes", "Pases"]
)

with tab_matches:
    st.write("Partidos que cumplen los filtros seleccionados:")
    match_columns = [
        "match_id",
        "match_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "competition_stage",
    ]
    visible_match_columns = [
        column for column in match_columns if column in filtered_matches.columns
    ]
    st.dataframe(
        filtered_matches[visible_match_columns],
        use_container_width=True,
        hide_index=True,
    )

with tab_events:
    st.write("Primeros eventos del partido seleccionado:")
    number_of_rows = st.slider("Filas que se mostrarán", 5, 100, 10)
    st.dataframe(events.head(number_of_rows), use_container_width=True)

    with st.expander("Ver nombres de todas las columnas"):
        st.write(list(events.columns))

with tab_missing:
    st.write(
        "En azul oscuro aparecen los datos faltantes. Muchos son normales: "
        "por ejemplo, las variables de pase quedan vacías cuando el evento es un tiro."
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(events.isna(), ax=ax, cbar=False, cmap="Blues")
    ax.set_xlabel("Variables")
    ax.set_ylabel("Eventos")
    ax.set_title("Mapa de datos faltantes")
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    missing_summary = (
        events.isna()
        .sum()
        .rename("datos_faltantes")
        .to_frame()
        .assign(porcentaje=lambda table: table["datos_faltantes"] / len(events) * 100)
        .sort_values("porcentaje", ascending=False)
    )
    st.dataframe(
        missing_summary.style.format({"porcentaje": "{:.2f}%"}),
        use_container_width=True,
    )

with tab_passes:
    pass_columns = [
        "minute",
        "second",
        "period",
        "location",
        "pass_end_location",
        "player",
        "pass_recipient",
        "team",
        "type",
    ]
    available_pass_columns = [
        column for column in pass_columns if column in events.columns
    ]

    # En el notebook original solo se seleccionaban columnas. Aquí también se
    # filtran las filas para conservar verdaderamente los eventos tipo "Pass".
    passes = events.loc[events["type"] == "Pass", available_pass_columns].copy()

    st.write(f"Se encontraron **{len(passes):,} pases** en este partido.")
    st.dataframe(passes, use_container_width=True, hide_index=True)

    st.download_button(
        "Descargar pases como CSV",
        data=passes.to_csv(index=False).encode("utf-8"),
        file_name=f"pases_partido_{match_id}.csv",
        mime="text/csv",
    )

st.caption("Fuente de datos: StatsBomb Open Data.")
