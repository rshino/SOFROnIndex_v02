#
'''
SOFR rates and index
RNS20220213

Run 2/25/2022
5 decimal precision (e.g., 1.234%)

min 1-day accrual 
count, errors, error_rate
123753, 272, 0.22%

min 21-day accrual 
count, errors, error_rate
114003, 88, 0.08%

min 63-day accrual 
count, errors, error_rate
94830, 46, 0.05%

'''


#
import numpy as np
import pandas as pd
import urllib.request
from datetime import datetime as dt, timedelta,date
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
import math
import os
from jinja2 import Template

TODAY=date.today()
START_DATE_SOFR_ON=dt(2018, 4, 2)
START_DATE_SOFR_INDEX=dt(2020, 3, 2)
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
    rows = [dt.strptime(dates[i].get_text(),'%Y-%m-%d'),float(rates[i].get_text())]
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
    loc=unique_index.get_loc(base_date,method=locdir)
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
  
#### functions ####

# get data from Fed 
# two queries because data ranges are different
sofrdf=fedQuery(SOFR_ON_REQCODE,SOFR_ON,START_DATE_SOFR_ON,TODAY) # SOFR ON
indexdf=fedQuery(SOFR_INDEX_REQCODE,SOFR_INDEX,START_DATE_SOFR_INDEX,TODAY) # SOFR Index
# combine into single series
alldf = pd.concat([sofrdf,indexdf],axis='columns',join='outer',ignore_index=False)
# add busday intervals between dates to series
dates=alldf.index
datelen=len(dates)
days=(dates[1:datelen]-dates[0:datelen-1]).days
days=days.append(pd.Index([math.nan])) # top off last day with null
alldf['days']=days # add days to df
# calculate dailyAccrual 
alldf['dailyAccrual']=(alldf[SOFR_ON]*alldf['days'])/(DAY_COUNT*100)+1.0

######################## setup complete #######################




TEST0=START_DATE_SOFR_INDEX
TEST1=TODAY #dt(2020, 6, 30) #TODAY
TEST1prevBD=dateShift(alldf,TEST1,FOLLOWING,-1)

testdates=alldf.loc[START_DATE_SOFR_INDEX:TEST1].index # accrual 
#stops 1 day before coupon date
testlen=len(testdates)
minimum_accruredBD=1



results = []
for i in range(testlen):
  d0=testdates[i]
  for j in range(i+1,testlen):
    d1=testdates[j]
    rate_compounded=rateSOFRon(alldf,d0,d1)
    rate_index=rateSOFRindex(alldf,d0,d1)
    rows = [d0,d1,(d1-d0).days,rate_compounded,rate_index]
    results.append(rows)
    
resultsdf = pd.DataFrame(results,columns = ['d0','d1','daysaccr','compounded','indexed'])

outputfile='SOFROnIndex_error.csv'
f=open(outputfile,"w")
f.write(', '.join(["precision","min_term","max_term","errors","samples","error_rate"])+'\n')
MAXTERM=9999
critical_terms=np.array([1,3,6]) # months

min_terms=np.round(np.append(0,np.append(np.append(0,critical_terms*253/12),critical_terms*253/12)),0)
max_terms=np.round(np.append(MAXTERM,np.append(np.append(critical_terms*253/12,MAXTERM),critical_terms*253/12)),0)

for precision in [ 3, 4, 5, 6 ]:
  for (min_term,max_term) in zip(min_terms,max_terms):
    samples=len(resultsdf[ (((resultsdf['daysaccr']>min_term) & (resultsdf['daysaccr']<max_term)) | \
                (resultsdf['daysaccr']==max_term))])
    if(samples>0):
      filtered = resultsdf[(round(resultsdf['compounded'],precision)!=round(resultsdf['indexed'],precision)) & \
        (((resultsdf['daysaccr']>min_term) & (resultsdf['daysaccr']<max_term)) | \
         (resultsdf['daysaccr']==max_term))]
      errors=len(filtered)
      pctfmt='{:.'+'{}'.format(precision-2)+'%}'
      print('precision=',precision,'min_term=',min_term,'max_term=',max_term,'error=',errors,'/', \
          samples,'=','{:.3%}'.format(errors/samples)) 
      f.write(', '.join(['{}'.format(precision),'{}'.format(min_term),'{}'.format(max_term), \
                       '{}'.format(errors),'{}'.format(samples),'{:.3%}'.format(errors/samples)])+'\n')
    #f.write(', '.join([precision,min_accrued,errors,count,float(errors/count)]+'\n'))

f.close()

pd.options.display.float_format = '{:0.10%}'.format
resultsdf.style.format({  'd0': '{:%Y-%m-%d}',  'd1': '{:%Y-%m-%d}' }) #,  'daysaccr':'{:d}'})
resultsdf.to_csv(path_or_buf='allresults.csv')

print("END")
