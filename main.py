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
  
  
def rateSOFRcleanindex(alldf,d0,d1):
  accrual_days = (d1-d0).days # calculated from 
  # next 3 lines calculates index0 without rounding
  d0prevBD=dateShift(alldf,d0,FOLLOWING,-1)
  accrualdf=alldf.loc[START_DATE_SOFR_ON:d0prevBD] 
  index0=accrualdf['dailyAccrual'].product()
  #
  #print('cleanindex=',index0)
  #print('index0=',alldf.loc[d0][SOFR_INDEX])
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

'''
d0 = dt(2021,12,10) 
d1 = d0+relativedelta(months=1)
print('  nominal dateStart=',date2ccyymmdd(d0))
print('    nominal dateEnd=',date2ccyymmdd(d1))
shift=-2
following=1
rounding=5 # meaning 3 for values expressed as %
d0=dateShift(alldf,d0,following, shift)
d1=dateShift(alldf,d1,following, shift)

rate_compounded=rateSOFRon(alldf,d0,d1)
rate_index=rateSOFRindex(alldf,d0,d1)
sample_value=0.001112113114115
if (not pd.isna(rounding)):
  rate_compounded=round(rate_compounded, rounding)
  rate_index=round(rate_index, rounding)
  sample_round=round(sample_value, rounding)
  pctfmt='{:.'+'{}'.format(rounding-2)+'%}'
else:
  sample_round=sample_value
  pctfmt='{:10%}'
#print('accrual(compounded)=',accrual_compounded)
#print('     accrual(index)=',accrual_index)
print('   rate(compounded)=',pctfmt.format(rate_compounded))
print('        rate(index)=',pctfmt.format(rate_index))

print('    rate difference=',pctfmt.format(rate_compounded-rate_index))
print('    rounding digits=',rounding,'sample ','{:.10%}'.format(sample_value),'-rounds to-> ',pctfmt.format(sample_round))
'''


TEST0=START_DATE_SOFR_INDEX
TEST1=dt(2020, 9, 30) #TODAY
TEST1prevBD=dateShift(alldf,TEST1,FOLLOWING,-1)

testdates=alldf.loc[START_DATE_SOFR_INDEX:TEST1].index # accrual 
testlen=len(testdates)
#stops 1 day before coupon date
count=0;error=0;
precision=5;  pctfmt='{:.'+'{}'.format(precision-2)+'%}'
minimum_accruredBD=1



results = []
for i in range(testlen):
  d0=testdates[i]
  for j in range(i+minimum_accruredBD,testlen):
    d1=testdates[j]
    count+=1
    rate_compounded=rateSOFRon(alldf,d0,d1)
    rate_index=rateSOFRindex(alldf,d0,d1)
    rows = [d0,d1,(d1-d0).days,rate_compounded,rate_index]
    results.append(rows)
    
    '''
    round_compounded=round(rate_compounded,precision)
    round_index=round(rate_index,precision)

    if((round_compounded-round_index)!=0):
      error+=1
      print('d0=',date2ccyymmdd(d0),'d1=',date2ccyymmdd(d1),'days accr.=','{}'.format((d1-d0).days) \
            ,'compounded=', pctfmt.format(round_compounded) \
            , 'indexed=' , pctfmt.format(round_index) \
           )

      
      f.write(', '.join([date2ccyymmdd(d0),date2ccyymmdd(d1),'{}'.format((d1-d0).days) \
                         ,pctfmt.format(round_compounded) \
                         ,pctfmt.format(round_index) \
                         ,'{:.10%}'.format(rate_compounded)
                         ,'{:.10%}'.format(rate_index) \
                         ,'{:.10%}'.format(rate_compounded-rate_index) \
                         ,'{:.9}'.format(alldf.loc[d0][SOFR_INDEX]) \
                         ,'{:.9}'.format(alldf.loc[d1][SOFR_INDEX]) \
                        ])+'\n')  
            '''


resultsdf = pd.DataFrame(results,columns = ['d0','d1','daysaccr','compounded','indexed'])

outputfile='test.csv'
print(outputfile)
f=open(outputfile,"w")
f.write(', '.join(["precision","min_accrued","errors","samples","error_rate"])+'\n')

for precision in [ 4, 5, 6 ]:
  for min_accrued in [ 1, 21, 63, 126 ]:
    samples=len(resultsdf[ (resultsdf['daysaccr']>=min_accrued)] )
    filtered = resultsdf[(round(resultsdf['compounded'],precision)!=round(resultsdf['indexed'],precision)) & \
    (resultsdf['daysaccr']>=min_accrued)]
    errors=len(filtered)
    pctfmt='{:.'+'{}'.format(precision-2)+'%}'
    print('precision=',precision,'min_accrued=',min_accrued,'error=',errors,'/', \
          samples,'=','{:.2%}'.format(error/samples))
    f.write(', '.join(['{}'.format(precision),'{}'.format(min_accrued),\
                       '{}'.format(errors),'{}'.format(samples),'{:.2%}'.format(errors/samples)])+'\n')
    #f.write(', '.join([precision,min_accrued,errors,count,float(errors/count)]+'\n'))

f.close()

'''
pd.options.display.float_format = pctfmt.format
filtered.style.format({  'd0': '{:%Y-%m-%d}',  'd1': '{:%Y-%m-%d}' }) #,  'daysaccr':'{:d}'})
#print(filtered)
#print(resultsdf)
filtered.to_csv()


f.write(', '.join(["d0","d1","daccr","compounded","indexed"
    ,"comp_precise"
    ,"index_precise" \
    ,"diff","index_d0","index_d1"])+'\n')


#f.write(', '.join(['count','errors','error_rate'])+'\n')
#f.write(', '.join(['{}'.format(count),'{}'.format(error),'{:.2%}'.format(error/count)])+'\n')
f.close()
'''
print("END")
