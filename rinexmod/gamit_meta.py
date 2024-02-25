#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  5 17:30:30 2024

@author: psakic

Low-level functions to import GAMIT metadata file as pandas DataFrame


"""

import numpy as np 
import pandas as pd
import datetime as dt
import re

from geodezyx import conv

p = "/home/psakicki/SOFTWARE/GAMIT10_7/210705/updates/source/tables/station.info.ray"
p = "/home/psakicki/SOFTWARE/GAMIT10_7/210705/updates/source/tables/station.info.sopac"
p = "/home/psakicki/Downloads/station.info"
p = "/home/psakicki/SOFTWARE/GAMIT10_7/210705/updates/source/tables/station.info.mit"


lfile_inp = "/home/psakicki/SOFTWARE/GAMIT10_7/210705/updates/source/tables/lfile."

def read_gamit_apr_lfile(aprfile_inp):
    """
    read a GAMIT's apr/lfile (GNSS stations coordinates and DOMES) 
    and store the data in a DataFrame    

    Parameters
    ----------
    aprfile_inp : str
        path of the input apr/lfile

    Returns
    -------
    df : pandas DataFrame
        the apr/lfile info data

    Note
    ----
    If no DOMES is provided in the last 'Note' column,
    a dummy DOMES 00000X000 is returned
    
    """
    lines_stk = []
    
    for l in open(aprfile_inp):
    
        if not l[0] == ' ':
            continue
        
        x, y, z  = np.nan,np.nan,np.nan
        #vx,vy,vz = 0.,0.,0.
        t = pd.NaT
    
        f = l[1:].split()
    
        site = l[1:5]
        site_full = f[0]
    
    
        x  = float(f[1])
        y  = float(f[2])
        z  = float(f[3])
        ttmp = float(f[7])
    
        # if np.isclose(ttmp , 0.):
        #     t = conv.year_decimal2dt(2000.)
        # else:
        #     t = conv.year_decimal2dt(ttmp)
        t = ttmp
    
        # if len(l) > 225: # if velocities are given (125 is arbitrary)
        #     vX = float(f[8])
        #     vY = float(f[9])
        #     vZ = float(f[10])
        # else: # if no velocityis given
        #     vX = 0.
        #     vY = 0.
        #     vZ = 0.
        
        domes_re = re.search('[0-9]{5}[A-Z][0-9]{3}',l)
        if domes_re:
            domes = domes_re.group()
        else:
            domes = '00000X000'
            
        lines_stk.append((site,site_full,t,x,y,z,domes))
        
    df = pd.DataFrame(lines_stk)
    df.columns = ['site','site_full','epoch','x','y','z','domes']
    
    return df


def read_gamit_station_info(station_info_inp):
    """
    read a GAMIT's station.info (GNSS stations metadata) 
    and store the data in a DataFrame
    
    Odd rows in station.info will be skipped

    Parameters
    ----------
    station_info_inp : str
        path of the input station.info.

    Returns
    -------
    df : pandas DataFrame
        the station info data

    """


    ### from gamit/lib/rstnfo.f
    #
    # c Label         Token  Format   Default      Description
    # c ------        -----  -----    ----------  ----------------------------------------------
    # c *SITE         sitcod  a4                  4-char station code 
    # c Station Name  sname   a16                 16-char station name
    # c Session Start  start  2i4,3i3  0 0 0 0 0  start time (yr doy hr min sec)
    # c Session Stop  stop    2i4,3i3  0 0 0 0 0  stop time (yr doy hr min sec)
    # c Sessn         sessn   i1       0          session number
    # c Ant Ht        anth    f7.4     0.0        height of antenna ARP above the monument
    # c Ant N         antn    f7.4     0.0        N offset of ant ARP from the center of the monument
    # c Ant E         ante    f7.4     0.0        E offset of ant ARP from the center of the monument
    # c RcvCod        rcvcod  a6                  6-char/acter GAMIT receiver code
    # c Receiver Type rctype  a20                 IGS (RINEX) receiver name    
    # c Receiver SN   rcvrsn  a20                 receiver serial number    
    # c SwVer         swver   f5.2     0.0        GAMIT firmware code (real)
    # c Vers          rcvers  a20                 receiver firmware version from RINEX
    # c AntCod        antcod   a6                 6-charr GAMIT antenna code     
    # c Antenna SN    antsn   a20                 20-char antenna serial number
    # c Antenna Type  anttyp  a15                 IGS antenna name, 1st 15 chars of RINEX antenna field
    # c Dome          radome   a5                 IGS radome name, last 5 chars of RINEX antenna field
    # c HtCod         htcod    a5     DHARP       5-char GAMIT code for type of height measurement
    # c AntDAZ	antdaz  f5.0     0.0        Alignment from True N (deg).  TAH 2020203. 
    
    
    
    
    #colsize = np.array([4,16,4,4,3,3,3,4,4,3,3,3,1,7,7,7,6,20,20,5,20,6,20,15,5,5,5])
    colsize = np.array([5,20,
                        4+1,3+1,2+1,2+1,2+1, # start
                        4+1,3+1,2+1,2+1,2+1, # end
                        7+2,7+2,7+2,6+2, # antenna high
                        20+2,20+2,5+2, # rec (2 version fields ...)
                        20+2, # rec SN
                        15+2,5+2, 20+2,1, # Antenna
                        ])
    
    
    #colsize_use = colsize+1
    colsize_use = colsize
    #colsize = [e+1  for e in colsize]
    #colsize_use = colsize+2
    
    col = ['site',
    'station name',
    'start year',
    'start doy',
    'start hh',
    'start mm',
    'start ss',
    'stop year',
    'stop doy',
    'stop hh',
    'stop mm',
    'stop ss',
    'htcod',
    'ant ht',
    'ant n',
    'ant e',
    #'rcvcod',
    'receiver type',
    'vers',
    'swver',
    'receiver sn',
    'antenna type',
    'dome',
    'antenna sn',
    'antdaz']
    
    df = pd.read_fwf(station_info_inp,
                     skiprows=10,
                     widths=colsize_use,
                     encoding = 'iso8859_1')

    df.columns = col 
    
    ##### clean df
    ### remove empty rows
    bool_empty_rows = df['site'].apply(len) < 4
    df = df[np.logical_not(bool_empty_rows)]
    ### do a second NaN cleaning, but the previous should have cleaned everything
    df.dropna(inplace=True,how='all')
    df.reset_index(inplace=True,drop=True)
    
    ##### create datetime start/end columns
    df['start doy'].replace(999,365,inplace=True)
    df['stop doy'].replace(999,365,inplace=True)
       

    df_start = conv.doy2dt(df['start year'],
                              df['start doy'],
                              df['start hh'],
                              df['start mm'],
                              df['start ss'])

    df['start'] = df_start

    df_end = conv.doy2dt(df['stop year'],
                         df['stop doy'],
                         df['stop hh'],
                         df['stop mm'],
                         df['stop ss'])

    df['end'] = df_end

    return df



df = read_gamit_station_info(p)


