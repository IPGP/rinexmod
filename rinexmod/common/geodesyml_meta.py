#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 2026-08-02

@author: psakic

Low-level functions to import GeodesyML metadata files and extract
instrumentation and site metadata.

"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime

import rinexmod.logger as rimo_log

logger = rimo_log.logger_define("INFO")


def _tryparsedate(date):
    """
    Parse a date string with multiple format support.
    
    Different date format to test on the string in case of bad standard compliance.
    If the date cannot be parsed, returns 'infinity' date (9999-01-01).
    """
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%MZ",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y/%m/%dT%H:%MZ",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%YT%H:%MZ",
        "%d/%m/%Y %H:%M",
        "%d/%m/%YT%H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
    ]
    if date:
        # Parse to date trying different formats
        for fmt in formats:
            try:
                date = datetime.strptime(date, fmt)
                break
            except:
                pass
    if not isinstance(date, datetime):
        # We set the date to 'infinity' date. If not a date, it's because it's an open border.
        date = datetime.strptime("9999-01-01", "%Y-%m-%d")

    return date


def parse_element(element):
    """
    Recursive function that traverses an XML element and converts it into a dictionary.
    If the element has no child elements, it returns the text content of the element.
    If the element has child elements, it iterates through each child and calls itself recursively to parse the child elements.
    The resulting dictionary is constructed based on the tag names of the child elements.
    If multiple child elements have the same tag name, their values are stored in a list.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element to be parsed

    Returns
    -------
    dict or str
    """

    if len(element) == 0:
        return element.text
    
    result = {}
    for child in element:
        text = parse_element(child)
        # when the same tag already exists
        if child.tag in result:
            # convert to list if not already
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(text)
        # gnssReceiver and gnssAntenna need to be lists even if single entry
        elif child.tag in ['gnssReceiver', 'gnssAntenna']:
            result[child.tag] = [text]
        # usual case, tag not existing yet
        else:
            result[child.tag] = text
    return result


def gml_file2raw(gmlfile):
    """
    Parse a GeodesyML file and convert it into a dictionary format.
    
    The function uses the ElementTree XML API to parse the GeodesyML file 
    and convert it into a dictionary format. It removes any XML namespaces 
    and antenna graphics information from the parsed data.

    Parameters
    ----------
    gmlfile : str
        Path to the GeodesyML file

    Returns
    -------
    dict
        A dictionary containing the structured information extracted from the GeodesyML file.
    """
    if not os.path.isfile(gmlfile):
        return None

    try:
        tree = ET.parse(gmlfile)
        root = tree.getroot()
    except:
        raise

    # removing namespace
    for elem in root.iter():
        tag = elem.tag
        if isinstance(tag, str) and tag.startswith('{'):
            tag = tag.split('}', 1)[1]
            elem.tag = tag

    # removing antenna graphics if any
    for elem in root.iter('moreInformation'):
        if elem.find('antennaGraphicsWithDimensions') is not None:
            elem.remove(elem.find('antennaGraphicsWithDimensions'))
        if elem.find('insertTextGraphicFromAntenna') is not None:
            elem.remove(elem.find('insertTextGraphicFromAntenna'))
   
    data_dict = {}
    data_dict = parse_element(root.find('siteLog'))

    # rounding float values of cartesian position to 3 decimals
    if 'siteLocation' in data_dict.keys():
        if 'approximatePositionITRF' in data_dict['siteLocation'].keys():
            if 'cartesianPosition' in data_dict['siteLocation']['approximatePositionITRF'].keys():
                if 'Point' in data_dict['siteLocation']['approximatePositionITRF']['cartesianPosition'].keys():
                    coords = data_dict['siteLocation']['approximatePositionITRF']['cartesianPosition']['Point']['pos'].split()
                    coords_rounded = [round(float(c), 3) for c in coords]
                    data_dict['siteLocation']['approximatePositionITRF']['cartesianPosition']['Point']['pos'] = ' '.join([str(c) for c in coords_rounded])
    return data_dict


def gml_raw2instrus(raw_content):
    """
    This function uses the raw_content dictionary (generated with gml_file2raw method) 
    to identify the different complete installations from the antenna and receiver change dates.

    Parameters
    ----------
    raw_content : dict
        Dictionary generated with gml_file2raw method

    Returns
    -------
    instrus : list
        List containing one or several dictionaries with keys 'dates', 'receiver', 'antenna'
    """

    listdates = []

    # parsing dates in gnssReceiver entries
    for receiver in raw_content['gnssReceiver']:
        receiver['GnssReceiver']['dateInstalled'] = _tryparsedate(receiver['GnssReceiver'].get('dateInstalled'))
        listdates.append(receiver['GnssReceiver']['dateInstalled'])
        receiver['GnssReceiver']['dateRemoved'] = _tryparsedate(receiver['GnssReceiver'].get('dateRemoved'))
        listdates.append(receiver['GnssReceiver']['dateRemoved'])

    # parsing dates in gnssAntenna entries
    for antenna in raw_content['gnssAntenna']:
        antenna['GnssAntenna']['dateInstalled'] = _tryparsedate(antenna['GnssAntenna'].get('dateInstalled'))
        listdates.append(antenna['GnssAntenna']['dateInstalled'])
        antenna['GnssAntenna']['dateRemoved'] = _tryparsedate(antenna['GnssAntenna'].get('dateRemoved'))
        listdates.append(antenna['GnssAntenna']['dateRemoved'])

    # remove duplicates and sort
    listdates = sorted(set(listdates))

    instrus = []

    for i in range(0, len(listdates)-1):
        dates = [listdates[i], listdates[i+1]]
        ins = dict(dates=dates, receiver=None, antenna=None, metpack=None)
        instrus.append(ins)

    for ins in instrus:
        for receiver in raw_content['gnssReceiver']:
            date_installed = receiver['GnssReceiver']['dateInstalled']
            date_removed = receiver['GnssReceiver']['dateRemoved']
            if date_installed <= ins['dates'][0] and date_removed >= ins['dates'][1]:
                ins['receiver'] = receiver['GnssReceiver']
                break

        for antenna in raw_content['gnssAntenna']:
            date_installed = antenna['GnssAntenna']['dateInstalled']
            date_removed = antenna['GnssAntenna']['dateRemoved']
            if date_installed <= ins['dates'][0] and date_removed >= ins['dates'][1]:
                ins['antenna'] = antenna['GnssAntenna']
                break
    
    return instrus


def gml_raw2misc_meta(raw_content, filename=None):
    """
    This function generates the "misc meta" dictionary containing all useful metadata 
    information which is not stored in the instrumentation dictionary.

    Parameters
    ----------
    raw_content : dict
        Dictionary generated with gml_file2raw method
    filename : str, optional
        Filename to extract site_id from. If provided and 9 chars, used for site_id.

    Returns
    -------
    dict : misc meta dictionary with keys: ID, IERS DOMES Number, operator, agency, X/Y/Z coordinates, date prepared, Country
    """
    
    if filename and len(filename) >= 9:
        site_id = filename[:9].upper()
    else:
        site_id = raw_content.get('siteIdentification', {}).get('siteName', 'UNKNOWN')
    
    domes = raw_content['siteIdentification']['iersDOMESNumber']
    operator = raw_content['siteContact']['name']
    agency = raw_content['moreInformation']['dataCenter']
    x, y, z = raw_content['siteLocation']['approximatePositionITRF']['cartesianPosition']['Point']['pos'].split(' ')
    date_prepared = _tryparsedate(raw_content['formInformation']['datePrepared'])
    country = raw_content['siteLocation']['countryCodeISO']

    misc_meta = dict(
        ID=site_id,
        **{"IERS DOMES Number": domes},
        operator=operator,
        agency=agency,
        **{"X coordinate (m)": float(x)},
        **{"Y coordinate (m)": float(y)},
        **{"Z coordinate (m)": float(z)},
        **{"date prepared": date_prepared},
        Country=country,
    )

    return misc_meta

