import streamlit as st
import re
import math
import pandas as pd

st.title("Calculateur d'administration des antibiotiques")


@st.cache_data
def load_data():
    try:
        df = pd.read_excel("antibiotics.xlsx")
        # Log the column names for debugging
        # st.write("Available columns in Excel file:", df.columns.tolist())

        # Convert DataFrame to dictionary format
        antibiotiques = {}
        for _, row in df.iterrows():
            try:
                # Skip empty or NaN entries for dilution_pratique
                dilution_str = str(row['Dilution pratique'])
                if pd.isna(dilution_str) or dilution_str.strip() == '':
                    continue

                # Debug: Print the dilution_pratique value
                # st.write(
                #     f"Debug - Dilution pratique for {row['Molécule']}: {dilution_str}")

                antibiotiques[row['Molécule']] = {
                    "stabilite": f"{row['Stabilité : en condition d\'hospitalisation']}h",
                    "dilution_pratique": row['Dilution pratique'],
                    "solute_de_dilution": row['Soluté de dilution'],
                    "duree_administration": str(row['Durée d\'administration si perfusion continue ou prolongée'])
                }
            except KeyError as e:
                st.error(f"Column missing in Excel file: {e}")
                return {}
        return antibiotiques
    except FileNotFoundError:
        st.error("Le fichier Excel 'antibiotics.xlsx' n'a pas été trouvé.")
        return {}
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier Excel: {str(e)}")
        return {}


# Load the data
antibiotiques = load_data()

# Choix du médicament
molecule = st.selectbox("Nom de la molécule", list(antibiotiques.keys()))

# Saisie de la dose totale par 24h (en grammes)
dose_24h = st.number_input("Dose totale par 24h (g)", min_value=0.0, step=0.1)

if st.button("Calculer"):
    if molecule not in antibiotiques:
        st.error("Molecule non trouvée dans la base de données.")
    elif dose_24h <= 0:
        st.error("La dose doit être supérieure à 0.")
    else:
        data = antibiotiques[molecule]

        # 1. Calculer le nombre d'infusions par jour à partir de la stabilité
        try:
            stability_hours = float(re.findall(r"(\d+)", data["stabilite"])[0])
        except IndexError:
            st.error("Erreur dans la donnée de stabilité.")
            st.stop()

        # Calcul : nombre d'infusions = 24 / durée de stabilité
        nb_infusion = int(24 / stability_hours)

        # Préparation d'une description textuelle de la fréquence
        nombre_text = {1: "une fois", 2: "deux fois", 3: "trois fois",
                       4: "quatre fois", 6: "six fois"}
        freq_text = f"1 perfusion toutes les {int(stability_hours)}h, {nombre_text.get(nb_infusion, str(nb_infusion) + ' fois')} par jour"

        # 2. Calculer le dosage par infusion
        dosage_infusion = dose_24h / nb_infusion

        # 3. Calculer le volume de dilution
        dilution_str = data["dilution_pratique"]
        # First pattern: "X à Y g dans Z ml"
        pattern1 = r"(\d+(?:[.,]\d+)?)\s*à\s*(\d+(?:[.,]\d+)?)\s*g\s*dans\s*(\d+(?:[.,]\d+)?)\s*ml"
        # Second pattern: "X g dans Y ml"
        pattern2 = r"(\d+(?:[.,]\d+)?)\s*g\s*dans\s*(\d+(?:[.,]\d+)?)\s*ml"

        match1 = re.search(pattern1, dilution_str)
        match2 = re.search(pattern2, dilution_str)

        try:
            if match1:
                max_val = float(match1.group(2).replace(",", "."))
                vol_ref = float(match1.group(3).replace(",", "."))
            elif match2:
                max_val = float(match2.group(1).replace(",", "."))
                vol_ref = float(match2.group(2).replace(",", "."))
            else:
                st.error("Le format de 'dilution_pratique' n'est pas reconnu.")
                st.stop()

            # Volume de dilution calculé selon la formule
            volume_dilution = dosage_infusion * vol_ref / max_val
            # Arrondir au multiple de 10 ml le plus proche
            volume_dilution_arrondi = int(round(volume_dilution/10.0))*10
        except ValueError:
            st.error("Erreur dans le format de 'dilution_pratique'.")
            st.stop()

        # 4. Extraire le soluté de dilution
        solute = data["solute_de_dilution"]

        # 5. Déterminer le matériel de perfusion
        if data["duree_administration"].strip().upper() == "NA":
            materiel = "IVL"
        else:
            materiel = "PSE" if volume_dilution_arrondi <= 50 else "pompe"

        # Préparation du message final en français
        resultat = (
            f"{molecule}, {dose_24h} g par 24h:\n\n"
            f"Détail de l'administration:\n"
            f"{dosage_infusion:.2f} g de {molecule}, diluée dans {volume_dilution_arrondi} ml de {solute}, "
            f"{freq_text}.\n"
            f"Volume de dilution: environ {volume_dilution_arrondi} ml\n"
            f"Matériel de perfusion: {materiel}"
        )

        st.success(resultat)

        with st.expander("ℹ️ Rationnel"):
            st.markdown("""
                        ##### Paramètres de stabilité et concentration
                        """)
            # Extraction de la concentration maximale depuis dilution_pratique
            if match1:
                conc_max = f"{match1.group(2)}g dans {match1.group(3)}ml"
            elif match2:
                conc_max = f"{match2.group(1)}g dans {match2.group(2)}ml"

            st.caption(f"""
                        • **Stabilité en condition d'hospitalisation:** {stability_hours}h
                        • **Concentration maximale recommandée:** {conc_max}
                    """)
