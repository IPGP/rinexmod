import pytest
from pathlib import Path
import gzip
import hatanaka
import rinexmod.api as rimo_api

rinex_in = Path(__file__).parent / "input" / "houz3000.25o"
sitelog_in = Path(__file__).parent / "input" / "houz00glp_20250106.log"
geodesy_gml_in = Path(__file__).parent / "input" / "HOUZ00GLP.xml"
correct_stlg_out = Path(__file__).parent / "output" / "correct_stlg" / "houz3000.25d.gz"
correct_gml_out = Path(__file__).parent / "output" / "correct_gml" / "houz3000.25d.gz"

TEST_CASES = [
    # rinex_in, rinex_out, parameters, correct_out
    (
        [rinex_in, "TMP"],
        {"sitelog": sitelog_in, "alone": True},
        correct_stlg_out
    ),
    (
        [rinex_in, "TMP"],
        {"geodesyml": geodesy_gml_in, "alone": True},
        correct_gml_out
    )
]

# use tmp_path in order to avoid writing to disk permanently
@pytest.mark.parametrize("inputs, parameters, correct_out", TEST_CASES)
def test_rinexmod_sitelog_gml(inputs, parameters, correct_out, tmp_path):
    
    current_pos_args = list(inputs)
    
    # convert Path objects to strings in parameters
    current_params = {}
    for key, value in parameters.items():
        if isinstance(value, Path):
            current_params[key] = str(value)
        else:
            current_params[key] = value

    if current_pos_args[1] == "TMP":
        current_pos_args[1] = str(tmp_path)

    rimo_api.rinexmod_cli(
        rinexinput=[str(current_pos_args[0])],
        outputfolder=current_pos_args[1],
        **current_params)

    output = list(tmp_path.glob("*.gz"))
    assert len(output) == 1

    compare_rinex_sections(output[0], correct_out)

def compare_rinex_sections(produced_path, expected_path):
    prod_section = get_section(produced_path)
    exp_section = get_section(expected_path)

    assert len(prod_section) == len(exp_section), "Header lengths differ!"
    for i, (p_line, e_line) in enumerate(zip(prod_section, exp_section)):
        assert p_line == e_line, f"Mismatch at line {i+1}:\nProduced: {p_line}\nExpected: {e_line}"

def get_section(file_path):
    
    lines = []

    with gzip.open(file_path, 'rb') as f:
        gzipped_content = f.read()

    try:
        # hatanaka.decompress returns bytes
        raw_rinex_bytes = hatanaka.decompress(gzipped_content)
        rinex_text = raw_rinex_bytes.decode("utf-8")
    except Exception as e:
        # try decoding the gzip content directly
        try:
            rinex_text = gzipped_content.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"Could not decompress or decode {file_path}: {e}")

    for line in rinex_text.splitlines():
            
        if any(label in line for label in ['MARKER NAME', 'MARKER NUMBER', 'OBSERVER / AGENCY', 'REC # / TYPE / VERS', 'ANT # / TYPE', 'APPROX POSITION XYZ', 'ANTENNA: DELTA H/E/N']):
            lines.append(line.rstrip())
        else:
            continue
        
        # stop when the section ends
        if "ANTENNA: DELTA H/E/N" in line:
            break

    return lines