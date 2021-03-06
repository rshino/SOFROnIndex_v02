#
'''
SOFR overnight rates and SOFR index

Calculates accruals using both methods, compares results after rounding
Compile error statistics
'''


#
import numpy as np
import pandas as pd
import urllib.request
import time
from datetime import datetime as dt, timedelta,date
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
#from html import HTML
import math
import os
from jinja2 import Template

TODAY=dt.now().date()
START_DATE_SOFR_ON=dt(2018, 4, 2).date()
START_DATE_SOFR_INDEX=dt(2020, 3, 2).date()
DAY_COUNT=360
# Fed data gleaned from XML links
# https://www.newyorkfed.org/markets/reference-rates/sofr
FEDMKT_URL='https://markets.newyorkfed.org/read'
SOFR_ON_REQCODE='520' 
SOFR_ON='percentRate'
SOFR_INDEX_REQCODE='525'
SOFR_INDEX='index'
FOLLOWING=1

def date2ccyymmdd(dateObj):
  return dt.strftime(dateObj,'%Y-%m-%d')

def fedQuery(rateCode, rateName,startDate,endDate):
  url_str = FEDMKT_URL+'?'+\
  '&startDt='+date2ccyymmdd(startDate)+\
  '&endDt='+date2ccyymmdd(endDate)+\
  '&productCode=50'+\
  '&eventCodes='+rateCode+'&sort=postDt:1&format=xml'
  request_url = urllib.request.urlopen(url_str)
  xmldata = request_url.read()
  soup = BeautifulSoup(xmldata,'xml')
  dates = soup.find_all('effectiveDate')
  rates = soup.find_all(rateName)
  data = []
  for i in range(0,len(dates)):
    rows = [dt.strptime(dates[i].get_text(),'%Y-%m-%d'),\
            float(rates[i].get_text())]
    data.append(rows)
  df = pd.DataFrame(data,columns = ['date',rateName])
  df.set_index('date',inplace=True,drop=True)
  return df
  # end fedQuery()

# dateShift(cal, base_date, match, shift)
#   given a base date (which may or may not be in cal) and 
#   cal        : dataframe busdays where index is datetime
#   base_date  : base date (e.g., coupon date)
#   match      : +1 find following date if no match (future)
#              : 0  exact date (returns None if not found)
#              : -1 find preceding date if no match (past)
#   shift      : number of busdays, shift>0 later, shift<0 earlier
def dateShift(cal, base_date, match=0, shift=0):
  if (match>0):
    locdir='bfill' # NEXT index value
  elif (match<0):
    locdir='ffill' # PREVIOUS index value
  else:
    locdir=None # exact
  unique_index=pd.Index(cal.index)
  maxloc=len(cal)
  try:
    #loc=unique_index.get_loc(base_date,method=locdir)
    #print('loc=',loc)
    loc=unique_index.get_indexer([base_date],method=locdir)[0]
    #print('loca2=',loc2)
    #loc=max(min(loc+shift,maxloc),0)
    #print(loc)
    return unique_index[loc+shift]
  except:
    return None

def rateSOFRon(alldf,d0,d1):
  d1prevBD=dateShift(alldf,d1,FOLLOWING,-1)
  accrualdf=alldf.loc[d0:d1prevBD] # accrual stops 1 day before coupon date
  accrual_days = (d1-d0).days # calculated from 
  accrual_compounded=accrualdf['dailyAccrual'].product()
  rate_compounded = (accrual_compounded-1)*360/accrual_days
  return rate_compounded

def rateSOFRindex(alldf,d0,d1):
  accrual_days = (d1-d0).days # calculated from 

  index0 = alldf.loc[d0][SOFR_INDEX]
  index1 = alldf.loc[d1][SOFR_INDEX]
  accrual_index=index1/index0
  rate_index = (accrual_index-1)*360/accrual_days
  return rate_index
  
#### end functions ####

# STEP 1. get data from Fed 
# two queries because data ranges are different
start = time.time()
sofrdf=fedQuery(SOFR_ON_REQCODE,\
                SOFR_ON,\
                START_DATE_SOFR_ON,\
                TODAY) # SOFR ON
indexdf=fedQuery(SOFR_INDEX_REQCODE,\
                 SOFR_INDEX,\
                 START_DATE_SOFR_INDEX,\
                 TODAY) # SOFR Index
end = time.time()
print('Acquired data from www.newyorkfed.org in ','{:0.1f}'.format(end-start), ' seconds.')
indexlen=len(indexdf)
# combine into single series
alldf = pd.concat([sofrdf,indexdf],axis='columns',\
                  join='outer',ignore_index=False)
# add busday intervals between dates to series
dates=alldf.index
datelen=len(dates)
days=(dates[1:datelen]-dates[0:datelen-1]).days
days=days.append(pd.Index([math.nan])) # top off last day with null
alldf['days']=days # add days to df
# calculate dailyAccrual 
alldf['dailyAccrual']=(alldf[SOFR_ON]*alldf['days'])/(DAY_COUNT*100)+1.0

#### setup complete, you can use alldf for all sorts of SOFR calculations #########

# STEP 2. calculate accruals
# this can take some time, as it run O(N^2)
# where N is days between TEST0 and TEST1
# adjust TEST0, TEST1 to shorten days for testing

TEST0=START_DATE_SOFR_INDEX # beginning of test period
TEST1=dt(2020, 6, 30).date() #TODAY   # end of test period set to TODAY for complete
TEST1prevBD=dateShift(alldf,TEST1,FOLLOWING,-1)

testdates=alldf.loc[START_DATE_SOFR_INDEX:TEST1].index # accrual 
#stops 1 day before coupon date
testlen=len(testdates)
minimum_accruredBD=1

print('Generating all SOFR accruals from ',TEST0,' to ', TEST1, ' (', testlen,' bus. days)')
if(indexlen-testlen>0):
  print('WARNING: Omitting ',indexlen-testlen,' bus. days from analysis,\n'
        '  in code set \n'
        '    TEST0=START_DATE_SOFR_INDEX and\n' 
        '    TEST1=TODAY \n'
        '  for complete range of accruals\n'
        '  Doing so may dramatically increase run times'
       )
results = []
start = time.time()

for i in range(testlen):
  d0=testdates[i]
  for j in range(i+1,testlen):
    d1=testdates[j]
    rate_compounded=rateSOFRon(alldf,d0,d1)
    rate_index=rateSOFRindex(alldf,d0,d1)
    rows = [d0,d1,(d1-d0).days,rate_compounded,rate_index]
    results.append(rows)
    
end = time.time()
print('Calculated ', len(results),' accruals in ','{:0.1f}'.format(end-start),' seconds')

resultsdf = pd.DataFrame(results,columns = \
                         ['d0','d1','daysaccr','compounded','indexed'])
# because there's typically too much data to print, we output raw unrounded results
# to csv file for verification using excel or whatever...
verify_output_file='allresults.csv'
if (len(verify_output_file)>0):
  pd.options.display.float_format = '{:0.10%}'.format
  resultsdf.style.format({  'd0': '{:%Y-%m-%d}',  'd1': '{:%Y-%m-%d}' }) #,  'daysaccr':'{:d}'})
  resultsdf.to_csv(path_or_buf=verify_output_file)

# STEP 3. compile and group differences
MAXTERM=9999
critical_terms=np.array([1,3,6]) # months

min_terms=np.round(np.append(0,np.append(np.append(\
  0,critical_terms*253/12),critical_terms*253/12)),0)
max_terms=np.round(np.append(MAXTERM,np.append(np.append(\
  critical_terms*253/12,MAXTERM),critical_terms*253/12)),0)

summary = []
for precision in [ 3, 4, 5, 6 ]:
  for (min_term,max_term) in zip(min_terms,max_terms):
    samples=len(resultsdf[ (((resultsdf['daysaccr']>min_term) & \
                             (resultsdf['daysaccr']<max_term)) | \
                (resultsdf['daysaccr']==max_term))])
    if(samples>0):
      filtered = resultsdf[(round(resultsdf['compounded'],precision)!=\
                            round(resultsdf['indexed'],precision)) & \
        (((resultsdf['daysaccr']>min_term) & (resultsdf['daysaccr']<max_term)) | \
         (resultsdf['daysaccr']==max_term))]
      errors=len(filtered)
      pctfmt='{:.'+'{}'.format(precision-2)+'%}'
      #print('precision=',precision,'min_term=',min_term,'max_term=',max_term,'error=',errors,'/', \
      #    samples,'=','{:.3%}'.format(errors/samples)) 
      row = [precision, int(min_term), int(max_term), int(errors), int(samples)]
      summary.append(row)
      
      #f.write(', '.join(['{}'.format(precision),'{}'.format(min_term),'{}'.format(max_term), \
      #                 '{}'.format(errors),'{}'.format(samples),'{:.3%}'.format(errors/samples)])+'\n')
    #f.write(', '.join([precision,min_accrued,errors,count,float(errors/count)]+'\n'))

#f.close()

# STEP 4. output results
summarydf = pd.DataFrame(summary,columns = \
                         ["prec","minterm","maxterm","errors","samples"])
summarydf['errate']=summarydf["errors"]/summarydf["samples"]
pd.options.display.float_format = '{:0.2%}'.format
summarydf.style.hide(axis='index')

print(summarydf.to_string(index=False))

print("END")
