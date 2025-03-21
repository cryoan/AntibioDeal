import streamlit as st
import pandas as pd
import re
import math
import streamlit_mermaid as stmd
import os

st.title("Antibiotic Dilution Calculator")

# Add help icon with SVG diagram
with st.expander("❓ Comment ça marche?"):
    try:
        with open("data/dilution_diagram.svg", "r") as file:
            svg_content = file.read()
            # Adjust height as needed
            st.components.v1.html(svg_content, height=1500)
    except Exception as e:
        st.error(f"Error displaying diagram: {e}")


@st.cache_data
def load_data():
    try:
        df = pd.read_excel("antibiotics_stability.xlsx")
        antibiotics = {}

        # Group by Molecule to handle duplicates
        for molecule, group in df.groupby('Molecule'):
            if len(group) > 0:  # If there's at least one entry
                antibiotics[molecule] = {
                    "variants": [
                        {
                            "solvent": row['Solvent'],
                            "concentration": row['Concentration'],
                            "stability": row['Stability'],
                            "comment": row['Comment'],
                            "reference": row['Reference']
                        }
                        for _, row in group.iterrows()
                        if not pd.isna(row['Concentration']) and str(row['Concentration']).strip() != ''
                    ]
                }
        return antibiotics
    except FileNotFoundError:
        st.error("Excel file 'antibiotics_stability.xlsx' not found.")
        return {}
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return {}


# Load the data
antibiotics = load_data()

# Select medication
molecule = st.selectbox("Molecule name", list(antibiotics.keys()))

if molecule:
    # Get all available solvents for this molecule
    variants = antibiotics[molecule]["variants"]

    # Create solvent selection if multiple variants exist
    if len(variants) > 1:
        solvent_options = [var["solvent"] for var in variants]
        selected_solvent = st.selectbox("Select solvent", solvent_options)
        # Find the selected variant
        data = next(
            var for var in variants if var["solvent"] == selected_solvent)
    else:
        # If only one variant, use it directly
        data = variants[0]

# Input total dose per 24h (in grams)
dose_24h = st.number_input("Total dose per 24h (g)", min_value=0.0, step=0.1)

if st.button("Calculate"):
    if molecule not in antibiotics:
        st.error("Molecule not found in database.")
    elif dose_24h <= 0:
        st.error("Dose must be greater than 0.")
    else:
        # 1. Calculate initial number of infusions based on stability
        try:
            stability_hours = float(re.findall(
                r"(\d+)\s*h", str(data["stability"]))[0])

            # Get maximum concentration
            concentration_str = str(data["concentration"])
            if "-" in concentration_str:
                max_val = float(re.findall(
                    r"(\d+(?:\.\d+)?)\s*mg/mL", concentration_str.split("-")[1])[0])
            else:
                max_val = float(re.findall(
                    r"(\d+(?:\.\d+)?)\s*mg/mL", concentration_str)[0])

            # Calculate minimum number of infusions based on stability
            min_infusions = int(24 / stability_hours)

            # Calculate if dose can fit in 50ml PSE
            dose_per_min_infusion = dose_24h / min_infusions  # in grams
            concentration_needed = (
                dose_per_min_infusion * 1000) / 50  # mg/mL in 50ml

            if concentration_needed <= max_val:
                # Can use PSE with minimum number of infusions
                nb_infusion = min_infusions
                volume_dilution = 50
                material = "PSE"
            else:
                # Need to try splitting into more infusions
                possible_infusions = []
                for n in range(min_infusions + 1, min_infusions * 2 + 1):
                    if 24 % n == 0:  # Must divide day evenly
                        hours_between = 24 / n
                        if hours_between <= stability_hours:  # Must respect stability
                            new_dose_per_infusion = dose_24h / n  # in grams
                            new_concentration = (
                                new_dose_per_infusion * 1000) / 50  # mg/mL in 50ml
                            if new_concentration <= max_val:
                                possible_infusions.append(n)

                if possible_infusions:
                    # Use the smallest number of infusions that works
                    nb_infusion = min(possible_infusions)
                    volume_dilution = 50
                    material = "PSE"
                else:
                    # Must use pump - calculate required volume based on concentration
                    nb_infusion = min_infusions
                    dose_per_infusion = dose_24h / nb_infusion  # in grams
                    # Calculate minimum volume needed to respect max concentration
                    # Round up to ensure concentration limit
                    volume_dilution = math.ceil(
                        (dose_per_infusion * 1000) / max_val)
                    # Round to nearest 10mL for pump
                    volume_dilution = math.ceil(volume_dilution / 10) * 10
                    material = "pompe"

            # Calculate hours between infusions
            hours_between = 24 / nb_infusion

            # Prepare text description of frequency
            number_text = {1: "once", 2: "twice", 3: "three times",
                           4: "four times", 6: "six times"}
            freq_text = f"1 infusion every {int(hours_between)}h, {number_text.get(nb_infusion, str(nb_infusion) + ' times')} per day"

            # Calculate final dosage per infusion
            dosage_infusion = dose_24h / nb_infusion

            # Prepare final message
            result = (
                f"{molecule}, {dose_24h} g per 24h:\n\n"
                f"Administration details:\n"
                f"{dosage_infusion:.2f} g of {molecule}, diluted in {volume_dilution} mL of {data['solvent']}, "
                f"{freq_text}.\n\n"
                f"Infusion material: {material}\n\n"
                f"Concentration: {(dosage_infusion * 1000 / volume_dilution):.1f} mg/mL\n\n"

                f"Maximum allowed concentration: {max_val} mg/mL\n"
            )

            # Add optimization note if applicable
            if nb_infusion > min_infusions:
                result += f"\n\nNote: Split into {nb_infusion} daily infusions to allow PSE usage (50mL)."

        except (IndexError, ValueError):
            st.error("Error in stability data format. Expected format: 'X h'")
            st.stop()

        st.success(result)

        with st.expander("ℹ️ Additional Information"):
            st.markdown("##### Stability and Concentration Parameters")
            st.caption(f"""
                • **Stability:** {data['stability']}
                • **Maximum concentration:** {data['concentration']}
                • **Comment:** {data['comment']}
                • **Reference:** {data['reference']}
            """)

# Read the Excel file
df = pd.read_excel("antibiotics_stability.xlsx")

# Display the first 10 rows
print("\nFirst 10 rows of antibiotics_stability.xlsx:")
print("=" * 80)
print(df.head(10))
print("\nDataframe Info:")
print("=" * 80)
print(df.info())
