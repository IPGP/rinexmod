#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 2026-01-XX

@author: psakic

Low-level functions to import rinexmod.info metadata file as pandas DataFrame
and convert to RinexMod internal objects.

The rinexmod.info is a CSV file containing metadata for GNSS sites
with fields similar to sitelogs (ISO 19115 standard).
One row per instrumental period per site.
"""

import datetime as dt
import os
import pandas as pd
import numpy as np

import rinexmod.api as rimo_api
import rinexmod.logger as rimo_log

logger = rimo_log.logger_define("INFO")


def read_rinexmod_info(rinexmod_info_inp, sort=True):
    """
    Read a rinexmod.info CSV file (GNSS stations metadata)
    and store the data in a DataFrame.

    Parameters
    ----------
    rinexmod_info_inp : str
        Path of the input rinexmod.info CSV file.
    sort : bool, optional
        Sort the DataFrame by site and start time.
        The default is True.

    Returns
    -------
    df : pandas DataFrame
        The rinexmod.info data with standardized column names.

    Note
    ----
    Site codes are given in lower case.
    Expected columns in the CSV (case-insensitive, with some flexibility):
    - site: 4-char site code
    - start/date_start: start date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    - end/date_end: end date (ISO 8601 format)
    - receiver_type: receiver model
    - receiver_sn/receiver_serial_number: receiver serial number
    - receiver_firmware/receiver_fw: receiver firmware version
    - antenna_type: antenna model
    - antenna_sn/antenna_serial_number: antenna serial number
    - antenna_ecc_up/antenna_arp_up: antenna height above marker (m)
    - antenna_ecc_north/antenna_arp_north: antenna north offset (m)
    - antenna_ecc_east/antenna_arp_east: antenna east offset (m)
    - antenna_daz/antenna_alignment: antenna alignment from True North (deg)
    - antenna_radome/dome: radome type
    - x/x_coord/antenna_x: X coordinate (m)
    - y/y_coord/antenna_y: Y coordinate (m)
    - z/z_coord/antenna_z: Z coordinate (m)
    - domes/domes_number: IERS DOMES number
    - country: ISO 3-letter country code
    - operator: station operator
    - agency: station agency
    """

    try:
        df = pd.read_csv(rinexmod_info_inp)
    except Exception as e:
        logger.error("Error reading rinexmod.info CSV file: %s", e)
        raise e

    # Normalize column names: lowercase, strip whitespace, replace common variants
    column_mapping = {}
    for col in df.columns:
        col_lower = col.strip().lower().replace(" ", "_").replace("-", "_")
        column_mapping[col] = col_lower

    df.rename(columns=column_mapping, inplace=True)

    # Standardize column names (handle common variants)
    col_aliases = {
        "date_start": ["start", "start_date"],
        "date_end": ["end", "end_date"],
        "receiver_sn": ["receiver_serial_number", "rcv_sn"],
        "receiver_firmware": ["receiver_fw", "rcv_fw", "fw_version"],
        "antenna_sn": ["antenna_serial_number", "ant_sn"],
        "antenna_ecc_up": ["antenna_arp_up", "antenna_height", "ant_ht", "antenna_arp_h", "antenna_ecc_h"],
        "antenna_ecc_north": ["antenna_arp_north", "antenna_n_offset", "ant_n", "antenna_arp_n"],
        "antenna_ecc_east": ["antenna_arp_east", "antenna_e_offset", "ant_e", "antenna_arp_e"],
        "antenna_daz": ["antenna_alignment", "ant_daz", "alignment_from_true_n"],
        "antenna_radome": ["dome", "radome"],
        "x_coord": ["x", "antenna_x"],
        "y_coord": ["y", "antenna_y"],
        "z_coord": ["z", "antenna_z"],
        "domes_number": ["domes"],
    }

    for standard_name, aliases in col_aliases.items():
        existing_cols = [c for c in df.columns if c in aliases]
        if len(existing_cols) > 0 and standard_name not in df.columns:
            df.rename(columns={existing_cols[0]: standard_name}, inplace=True)

    # Ensure required columns exist
    required_cols = ["site", "date_start", "date_end", "receiver_type", "antenna_type"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        logger.error("Missing required columns in rinexmod.info: %s", missing_cols)
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Process dates: convert to datetime
    try:
        df["date_start"] = pd.to_datetime(df["date_start"])
        df["date_end"] = pd.to_datetime(df["date_end"])
    except Exception as e:
        logger.error("Error converting dates in rinexmod.info: %s", e)
        raise e

    # Standardize site codes to lowercase
    df["site"] = df["site"].str.lower()

    # Handle numeric columns with NaN defaults
    numeric_cols = [
        "antenna_ecc_up",
        "antenna_ecc_north",
        "antenna_ecc_east",
        "antenna_daz",
        "x_coord",
        "y_coord",
        "z_coord",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill NaN values with defaults where appropriate
    defaults = {
        "antenna_ecc_up": 0.0,
        "antenna_ecc_north": 0.0,
        "antenna_ecc_east": 0.0,
        "antenna_daz": 0.0,
        "receiver_sn": "none",
        "receiver_firmware": "none",
        "antenna_sn": "none",
        "antenna_radome": "NONE",
        "domes_number": "00000X000",
        "operator": "OPERATOR",
        "agency": "AGENCY",
        "country": "XXX",
    }

    for col, default_val in defaults.items():
        if col in df.columns:
            if isinstance(default_val, str):
                df[col] = df[col].fillna(default_val)
            else:
                df[col] = df[col].fillna(default_val)

    # Ensure x, y, z coordinates exist (fake if missing)
    for coord in ["x_coord", "y_coord", "z_coord"]:
        if coord not in df.columns:
            if coord == "x_coord":
                df[coord] = 6378137.000  # Earth's semi-major axis
            else:
                df[coord] = 0.0

    if sort:
        df.sort_values(by=["site", "date_start"], inplace=True)

    df.reset_index(drop=True, inplace=True)

    return df


def rinexmod_df2instru_miscmeta(site, rinexmod_df_inp, force_fake_coords=False):
    """
    Convert rinexmod.info DataFrame to RinexMod internal
    "instrus" and "misc_meta" dictionaries for a specific site.

    Parameters
    ----------
    site : str
        4-char or 9-char site code to extract from DataFrame.
    rinexmod_df_inp : pd.DataFrame
        rinexmod.info DataFrame.
    force_fake_coords : bool, optional
        If True, coordinates will be set to (0,0,0) and
        DOMES to 00000X000. The default is False.

    Returns
    -------
    installations : list
        List of "instrus" dicts for each instrumental period.
    mm_dic : dict
        "misc_meta" dict with site coordinates and metadata.
    """

    # Extract 4-char site code if 9-char is given
    site_4char = site[:4].lower()

    # Filter DataFrame for this site
    rinexmod_df_site = rinexmod_df_inp[
        rinexmod_df_inp["site"] == site_4char
    ].copy()

    if len(rinexmod_df_site) == 0:
        logger.error("Site %s not found in rinexmod.info", site)
        if not force_fake_coords:
            raise rimo_api.RinexModError(f"Site {site} not found in rinexmod.info")
        else:
            # Create dummy installation with fake coordinates
            inst_dic = {
                "dates": [
                    dt.datetime(2000, 1, 1),
                    dt.datetime(2099, 12, 31),
                ],
                "receiver": {
                    "Receiver Type": "UNKNOWN",
                    "Satellite System": "GPS+GLO+GAL+BDS+QZSS+SBAS",
                    "Serial Number": "none",
                    "Firmware Version": "none",
                    "Elevation Cutoff Setting": "0",
                    "Date Installed": dt.datetime(2000, 1, 1),
                    "Date Removed": dt.datetime(2099, 12, 31),
                    "Temperature Stabiliz.": "none",
                    "Additional Information": "none",
                },
                "antenna": {
                    "Antenna Type": "UNKNOWN",
                    "Serial Number": "none",
                    "Antenna Reference Point": "none",
                    "Marker->ARP Up Ecc. (m)": 0.0,
                    "Marker->ARP North Ecc(m)": 0.0,
                    "Marker->ARP East Ecc(m)": 0.0,
                    "Alignment from True N": 0.0,
                    "Antenna Radome Type": "NONE",
                    "Radome Serial Number": "none",
                    "Antenna Cable Type": "none",
                    "Antenna Cable Length": "0",
                    "Date Installed": dt.datetime(2000, 1, 1),
                    "Date Removed": dt.datetime(2099, 12, 31),
                    "Additional Information": "none",
                    "metpack": "none",
                },
            }
            installations = [inst_dic]
            mm_dic = {
                "IERS DOMES Number": "00000X000",
                "operator": "OPERATOR",
                "agency": "AGENCY",
                "X coordinate (m)": 6378137.000,
                "Y coordinate (m)": 0.0,
                "Z coordinate (m)": 0.0,
                "ID": site_4char,
                "Country": "XXX",
            }
            return installations, mm_dic

    # Build installations list from each row
    installations = []
    last_x, last_y, last_z, last_domes = None, None, None, None

    for irow, row in rinexmod_df_site.iterrows():
        inst_dic = {}

        # Dates
        inst_dic["dates"] = [
            row["date_start"].to_pydatetime(),
            row["date_end"].to_pydatetime(),
        ]

        # Receiver
        rec_dic = {
            "Receiver Type": str(row.get("receiver_type", "UNKNOWN")),
            "Satellite System": "GPS+GLO+GAL+BDS+QZSS+SBAS",
            "Serial Number": str(row.get("receiver_sn", "none")),
            "Firmware Version": str(row.get("receiver_firmware", "none")),
            "Elevation Cutoff Setting": "0",
            "Date Installed": row["date_start"].to_pydatetime(),
            "Date Removed": row["date_end"].to_pydatetime(),
            "Temperature Stabiliz.": "none",
            "Additional Information": "none",
        }
        inst_dic["receiver"] = rec_dic

        # Antenna
        ant_dic = {
            "Antenna Type": str(row.get("antenna_type", "UNKNOWN")),
            "Serial Number": str(row.get("antenna_sn", "none")),
            "Antenna Reference Point": "none",
            "Marker->ARP Up Ecc. (m)": row.get("antenna_ecc_up", 0.0),
            "Marker->ARP North Ecc(m)": row.get("antenna_ecc_north", 0.0),
            "Marker->ARP East Ecc(m)": row.get("antenna_ecc_east", 0.0),
            "Alignment from True N": row.get("antenna_daz", 0.0),
            "Antenna Radome Type": str(row.get("antenna_radome", "NONE")),
            "Radome Serial Number": "none",
            "Antenna Cable Type": "none",
            "Antenna Cable Length": "0",
            "Date Installed": row["date_start"].to_pydatetime(),
            "Date Removed": row["date_end"].to_pydatetime(),
            "Additional Information": "none",
            "metpack": "none",
        }
        inst_dic["antenna"] = ant_dic

        installations.append(inst_dic)

        # Keep track of last coordinates for misc_meta
        last_x = row.get("x_coord", 6378137.000)
        last_y = row.get("y_coord", 0.0)
        last_z = row.get("z_coord", 0.0)
        last_domes = row.get("domes_number", "00000X000")

    # Misc metadata (use last row's coordinates)
    if force_fake_coords or all(pd.isna([last_x, last_y, last_z])):
        last_x = 6378137.000
        last_y = 0.0
        last_z = 0.0
        last_domes = "00000X000"

    mm_dic = {
        "IERS DOMES Number": str(last_domes),
        "operator": str(rinexmod_df_site.iloc[-1].get("operator", "OPERATOR")),
        "agency": str(rinexmod_df_site.iloc[-1].get("agency", "AGENCY")),
        "X coordinate (m)": float(last_x) if not pd.isna(last_x) else 6378137.000,
        "Y coordinate (m)": float(last_y) if not pd.isna(last_y) else 0.0,
        "Z coordinate (m)": float(last_z) if not pd.isna(last_z) else 0.0,
        "ID": site_4char,
        "Country": str(rinexmod_df_site.iloc[-1].get("country", "XXX")),
    }

    return installations, mm_dic
