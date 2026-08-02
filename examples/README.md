# rinexmod.info Example File

This directory contains an example of a `rinexmod.info` CSV file that demonstrates the format for providing GNSS site metadata to rinexmod.

## File Structure

The `rinexmod.info.example` file contains metadata for 5 sites (houz, abcd, jplm, drvs, test) with multiple instrumental periods for some sites.

### Sites in the Example:

1. **houz** (France - IPGP)
   - 3 instrumental periods (2010-2025)
   - Receiver changes: LEICA GR50 → LEICA GR50 → TRIMBLE NETR9
   - Antenna changes: ASH701945G_M → ASH701945G_M → ASH700936D_M

2. **abcd** (USA - IGN)
   - 2 instrumental periods (2015-2025)
   - Consistent receiver: SEPT POLARX5
   - Consistent antenna: LEIAR25.R4

3. **jplm** (USA - JPL/NASA)
   - 1 continuous period (2018-2025)
   - Receiver: JAVAD TRIUMPH-1 X
   - Antenna: TRM59800.80

4. **drvs** (Australia)
   - 2 instrumental periods (2012-2025)
   - Receiver changes: LEICA GR25 → TRIMBLE NET-G6
   - Antenna changes: ASH701945C_M → TRM57971.00

5. **test** (Canada)
   - 2 instrumental periods (2020-2025)
   - Receiver changes: SEPT POLARX4 → SEPT POLARX5
   - Antenna changes: ASH701945A_M → LEIAR10.R4

## Usage

### Command Line
```bash
rinexmod_run -i input_rinex_files.list \
             -o output_folder \
             --rinexmod_info /path/to/rinexmod.info.example
```

### Python API
```python
import rinexmod.api as rimo_api

rimo_api.rinexmod_cli(
    rinexinput=["houz*.rnx.gz"],
    outputfolder="output/",
    rinexmod_info="rinexmod.info.example"
)
```

## Column Descriptions

| Column | Description | Example | Required |
|--------|-------------|---------|----------|
| site | 4-character GNSS site code | houz | Yes |
| date_start | Start date/time (ISO 8601) | 2010-01-01T00:00:00 | Yes |
| date_end | End date/time (ISO 8601) | 2015-06-30T23:59:59 | Yes |
| receiver_type | Receiver model name | LEICA GR50 | Yes |
| receiver_sn | Receiver serial number | 1234567 | No |
| receiver_firmware | Receiver firmware version | 4.51 | No |
| antenna_type | Antenna model name | ASH701945G_M | Yes |
| antenna_sn | Antenna serial number | S001 | No |
| antenna_ecc_up | Antenna height above marker (m) | 1.2 | No |
| antenna_ecc_north | Antenna north offset (m) | 0.0 | No |
| antenna_ecc_east | Antenna east offset (m) | 0.0 | No |
| antenna_daz | Antenna alignment from True North (deg) | 0.0 | No |
| antenna_radome | Antenna radome type | LEIS | No |
| x_coord | X coordinate in ECEF (m) | 4000894.7571 | No* |
| y_coord | Y coordinate in ECEF (m) | 611081.9633 | No* |
| z_coord | Z coordinate in ECEF (m) | 4966890.0318 | No* |
| domes_number | IERS DOMES number | 10002M001 | No |
| operator | Station operator | OVS | No |
| agency | Station agency | IPGP | No |
| country | ISO 3-letter country code | FRA | No |

*Coordinates are required unless using `--force_fake_coords` option

## Notes

- **One row per instrumental period**: If a site has multiple receiver or antenna changes, create separate rows with different date ranges
- **Date format**: Must be ISO 8601 format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)
- **Column flexibility**: Column names are case-insensitive and accept common aliases (e.g., "date_start", "start", "start_date")
- **Default values**: Missing optional fields will be filled with sensible defaults
- **Coordinates**: Should be in ECEF (Earth-Centered, Earth-Fixed) format in meters

## Tips for Creating Your Own

1. Start with this example file as a template
2. Add your sites and their metadata
3. Keep dates non-overlapping for the same site
4. Verify all required fields are filled
5. Test with a small set of RINEX files first
6. Use dates that encompass your RINEX file periods

## Validation

To validate your rinexmod.info file before using it:

```python
from rinexmod.readers.rinexmod_info_meta import read_rinexmod_info
import pandas as pd

# Read and validate
try:
   df = read_rinexmod_info('your_rinexmod.info')
   print("✓ File is valid")
   print(f"  Sites: {df['site'].unique()}")
   print(f"  Periods: {len(df)}")
except Exception as e:
   print(f"✗ Validation error: {e}")
```

---

For more information, see the [rinexmod README](../README.md#rinexmodinfo-csv-format).
