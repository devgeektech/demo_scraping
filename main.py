import logging
import time
import os
import shutil
import sys
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.chrome.service import Service as ChromeService 
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from fastapi import FastAPI, Response, Request
import uvicorn
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import pandas as pd
from bs4 import BeautifulSoup
from checkLoginError import authenticateUserDetail
import json
import csv

import threading
import requests

wookaiApiUrl = 'node_api_url'

#Provide domain, so the spider does not follow external links
URL = 'your_url_to_scrap'

cur_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(cur_dir, 'logs')
local_tmp_folder = os.path.join(cur_dir, 'static')

# FastAPI starts here
# FastAPI docs description
description = """
Export the Order CSV using Selenium
"""

# initialization of fastapi app
app = FastAPI(
    title = "Lisanti order export Automation",
    description = description,
    version = "0.0.1",
    contact = {
        "name": "Lisanti",
    },
)

app.mount("/static", StaticFiles(directory="static"), name="static")

def getOptions(file_path):
    chromeOptions = Options()
    chromeOptions.add_experimental_option(
        "prefs", {"download.default_directory": file_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True, "safebrowsing.enabled": True
        }
    )
    
    chromeOptions.add_argument("start-maximized")
    chromeOptions.add_argument("disable-infobars")
    chromeOptions.add_argument("--disable-extensions")
    chromeOptions.add_argument('--headless')
    chromeOptions.add_argument('--disable-gpu')
    chromeOptions.add_argument('--no-sandbox')
    chromeOptions.add_argument("window-size=1200,1100")
    return chromeOptions
       
def setup_logger():
    logging.basicConfig(
        filemode='w', filename=os.path.join(logs_dir, "site_to_site.log"),
        format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO
    )

    alogger = logging.getLogger("site_to_site")


setup_logger()
logger = logging.getLogger("site_to_site")

# Convert Html Table to csv 
def converToCsv(nUsername,file, username_folder):
    
    data = []
    path = file
    # for getting the header from
    # the HTML file
    list_header = []
    soup = BeautifulSoup(open(path),'html.parser')
    header = soup.find_all("table")[0].find("tr")
    
    for items in header:
        try:
            list_header.append(items.get_text())
        except:
            continue
    
    # for getting the data
    HTML_data = soup.find_all("table")[0].find_all("tr")[1:]
    
    for element in HTML_data:
        sub_data = []
        for sub_element in element:
            
            try:
                sub_data.append(sub_element.get_text().strip('\n'))
                sub_data = [ele for ele in sub_data if ele.strip()]
                sub_data.split('/')
            except:
                continue
        data.append(sub_data)
    list_header =  list_header[: len(list_header) - 2]
    dataFrame = pd.DataFrame(data = data, columns = list_header)
    # dataFrame['Pack/Size'].str.split('/')
    # dataFrame['Pack/Size'].str.split('/', expand=True)
    dataFrame[['Pack','desiremove']]=dataFrame["Pack/Size"].str.split("/",expand=True)
    dataFrame[['Size','Designated']]=dataFrame["desiremove"].str.split("#",expand=True)
    dataFrame.drop(['Pack/Size','desiremove'], inplace=True, axis=1)
    dataFrame = dataFrame[['Item','Description','Pack','Size','Designated','Price']]

    # Converting Pandas DataFrame into CSV file
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    newFileName = f"{username_folder}/export.csv"
    # newFileName = os.path.join(BASE_DIR,newFileName)
    dataFrame.to_csv(newFileName, index = False)
    dataFrame.to_csv(newFileName, index = False)

    logger.info("Converted data to CSV.")
    return newFileName

# Format products
def formatProducts(nUsername,products, username_folder):
    
    logger.info("Formatting products")
    products = ''.join(products)        
    #open Html file and write table html on it
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    newFileName = username_folder + "/table.html"
    newFileName = os.path.join(BASE_DIR,newFileName)
    with open(newFileName, 'w') as file:
        file.write(products)           
    
    time.sleep(5)
    
    # Format the Table html and remove unnecessary data from it
    newFileName = username_folder + "/table.html"
    newFileName = os.path.join(BASE_DIR,newFileName)
    soup = BeautifulSoup(open(newFileName),'html.parser')

    items = ['<tr class="black_bold_back"><td width="60">Item</td><td width="275">Description</td><td width="100">Pack/Size</td><td width="85">Price</td><td>Qty   </td><td></td></tr>']
    html = soup.findAll("tr", {"onmouseover" : "style.backgroundColor='#004fff';"})

    for el in html:
        items.append(el)
    
    products = ' '.join([str(elem) for elem in items])
    products = products.strip('\n')
    products = "<table>" + products + "</table>"
    
    #Save the Filtered html table
    newFileName = username_folder + "/filtered_table.html"
    newFileName = os.path.join(BASE_DIR,newFileName)
    with open(newFileName, 'w') as file:
        file.write(products)
    
    # create Html table to csv
    csvConversion = converToCsv(nUsername,newFileName, username_folder)
    logger.info("Crawled successfully")
    return csvConversion


def seleniumCallback(nUsername, nPassword, vendorId):    


    # name of the static folder
    static_folder = 'static'

    # create a timestamp folder under the static folder
    timestamp = int(time.time())
    timestamp_folder = os.path.join(static_folder, str(timestamp))
    os.mkdir(timestamp_folder)

    # create a username folder under the timestamp folder    
    username_folder = os.path.join(timestamp_folder, nUsername)
    os.mkdir(username_folder)
    file_path = os.path.join(cur_dir, username_folder)
    logging.info(f"Download file path: {file_path}")

    # driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=getOptions(file_path))
    driver_service = Service(executable_path="/var/www/html/chrome_driver/chromedriver")
    driver = webdriver.Chrome(service=driver_service, options=getOptions(file_path))
    logger.info('Selenium webdriver created')
    logger.info(f'Username: {nUsername}')
    try:
        
        driver.get(URL)
        logger.info('Loading site')
        time.sleep(5)

        #Fill the username and password
        try:  
            username = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="table2"]/tbody/tr[1]/td[2]/input'))
            )
            username.send_keys(nUsername)
            logger.info("Filled username field.")
        except:
            logger.info("Not found username field.")
            # Return false response to wookai Server
            returnResponseToServer(False,"Not found username field.",nUsername,vendorId,None)
            driver.quit()
            return False
            
        try:  
            password = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="table2"]/tbody/tr[2]/td[2]/input'))
            )
            password.send_keys(nPassword)
            logger.info("Filled password field.")
        except:
            logger.info("Not found password field.")
            # Return false response to wookai Server
            returnResponseToServer(False,"Not found password field.",nUsername,vendorId,None)
            driver.quit()
            return False     

        # submit button
        try:
            button = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="table2"]/tbody/tr[3]/td[2]/input'))
            )
            button.click()
            logger.info('Login button clicked')
        except:            
            logger.info('Login form button not found')
            # Return false response to wookai Server
            returnResponseToServer(False,"Login form button not found.",nUsername,vendorId,None)
            driver.quit()
            return False
        
        time.sleep(2)
        
        # Check if "orders button" is visible or not
        try:  
            orders_btn = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '/html/body/table[2]/tbody/tr/td[1]/table/tbody/tr[1]/td/a'))
            )
            orders_btn.click()
            logger.info("Orders button is clicked.")
        except:
            logger.info("Orders button is not visible.")
        
        time.sleep(2)

        # Check if "table exists" is visible
        try:  
            table_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '/html/body/table[2]/tbody/tr[2]/td'))
            )
            products = table_element.get_attribute("innerHTML")         
            logger.info("Scraping table data.")            
            # Put products into html file
            downloadedFilename = formatProducts(nUsername,products, username_folder)
            time.sleep(15)
            logger.info('File is downloaded')
            # Return false response to wookai Server
            returnResponseToServer(False,"File is downloaded",nUsername,vendorId,None)
            driver.quit()
            
            # Prepare downloaded file
            logger.info(f'Downloaded file path in callselenium is : {downloadedFilename}')
            return downloadedFilename
        except Exception as e:
            logger.info("Table is not visible.")
            logger.info(e)
            # Return false response to wookai Server
            returnResponseToServer(False,"Table is not visible.",nUsername,vendorId,None)
            driver.quit()
            return False

    except:
        logger.info("Some element not found.")
        # Return false response to wookai Server
        returnResponseToServer(False,"Some element not found.",nUsername,vendorId,None)
        driver.quit()
        return False


def returnResponseToServer(success,message,username,vendorId,csv_file):
    try:
        logger.info(message) 
        if success != False:           
            logger.info(f'Uploading csv file: {csv_file}')

        url = wookaiApiUrl
        payload = {'success':success,'username': username,"vendorId": vendorId,"csv":csv_file} 
        return False
        x = requests.post(url, json = payload) 
        logger.info(f'x: {x}')
            
    except Exception as ex:
        logger.info(f'Exception in returnResponseToServer(): {ex}')
        

# Check if CSV is blank or not
def checkCSV(csv_file):
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)
        if len(rows) > 0:
            return True
        else:
            return False

# Get latest file
# def getLatestFile(username):
#     setup_logger()
#     logger = logging.getLogger("site_to_site")
#     try:        
#         currentTime = str( time.time() )
#         filename = max([local_tmp_folder + "/" + f for f in os.listdir(local_tmp_folder)],key=os.path.getctime)
#         shutil.move(filename,os.path.join(local_tmp_folder,r"file_" + currentTime + '_'+ username + ".csv"))
#         fileName = r"static/file_" + currentTime + '_'+ username + ".csv"        
#         logger.info(f'Renamed downloaded csv file path: {fileName}')      
#         # Check if CSV is blank or not
#         is_csv_not_blank = checkCSV(fileName)
#         if is_csv_not_blank:
#             logger.info('CSV file is not blank')
#             return fileName
#         else:
#             logger.info('CSV file is blank')
#             return None
#     except Exception as ex:
#         logger.info(f'Exception: {ex}')
#         return None


def getLatestFile(filePath):
   
    try:
        # Check if CSV is blank or not
        fileName = filePath
        is_csv_not_blank = checkCSV(fileName)
        if is_csv_not_blank:
            logger.info(f'CSV file is not blank: {fileName}')
            return fileName
        else:
            logger.info(f'CSV file is blank: {fileName}')
            return None
    except Exception as ex:
        logger.info(f'Exception in getLatestFile(): {ex}')
        return None
        

# accept the API parameters
class UserParamas(BaseModel):
    username: str
    password: str
    vendorId: str

# accept the API parameters 
class AuthParams(BaseModel):
    username: str
    password: str
    supplier: str

# API home Route
@app.get("/")
async def home():
    return "Lisanti order automation"

# * run the scrapy command to scrap the data 
@app.post("/export-data")
async def root(params:UserParamas, request:Request):
    
    # Scrape data task
    def scrape_data(): 
        if params.username is not None and params.password is not None:
            if "twisted.internet.reactor" in sys.modules:
                del sys.modules["twisted.internet.reactor"]       
            
            try:
                callSelenium = seleniumCallback(params.username, params.password,params.vendorId)
                if callSelenium != False:
                    downloadedFile = getLatestFile(callSelenium)
                    if downloadedFile is not None:

                        filePath = request.base_url._url+downloadedFile
                        
                        # Respond back to the server
                        returnResponseToServer(True,None,params.username,params.vendorId,filePath)
                        
                        response = {
                            'success' : True,
                            'data' : filePath,
                            'message' : 'Data scrapped successfully.'
                        }
                        return response
                    else:
                        response = {
                            'success' : False,
                            'data' : None,
                            'message' : 'Downloaded file is blank.'
                        }
                        return response
                else:
                    response = {
                        'success' : False,
                        'data' : None,
                        'message' : "This supplier's site is under maintenance or requires you to log in and respond to a message regarding your account."
                    }

                return response
            except Exception as e:
                logging.critical(e, exc_info=True)
                response = {
                    'success' : False,
                    'data' : '',
                    'message' : "This supplier's site is under maintenance or requires you to log in and respond to a message regarding your account."
                }
                return response
        else:
            response = {
                'success' : False,
                'data' : '',
                'message' : 'Username & Password are invalid.'
            }
            return response

    t = threading.Thread(target=scrape_data)
    t.start()
    return {"success": True, "message": "Your scraping request is processing in background thread."} 

# Get export file
@app.get("/get-export-file")
async def getExportFile(request:Request):
    downloadedFile = getLatestFile()
    filePath = request.base_url._url +'/files/'+ downloadedFile
    return filePath


# check if username and password are wrong
@app.post("/authenticate")
async def authenticateUserLogin(params:AuthParams, request: Request):
    
    if params.username is not None and params.password is not None and params.supplier is not None:
        if "twisted.internet.reactor" in sys.modules:
            del sys.modules["twisted.internet.reactor"]

        try:
            authenticateUser = authenticateUserDetail(params.username, params.password, params.supplier)

            if authenticateUser == True:
                response = {
                    'responseCode' : 200,
                    'message' : 'User authenticated successfully',
                    'data' : {
                        'success' : True,
                        'supplier' : params.supplier,
                        
                    }
                }
            else:
                response = {
                    'responseCode' : 400,
                    'message' : 'The login detail is not valid',
                    'data' : {
                        'success' : False,
                        'supplier' : params.supplier,
                    }
                }
        except:
            response = {
                'responseCode' : 400,
                'message' : 'Something went wrong',
                'data' : {
                    'success' : False,
                    'supplier' : params.supplier,                        
                }
            }
    else:
        response = {
                'responseCode' : 400,
                'message' : 'Username and password not found',
                'data' : {
                    'success' : False,
                    'supplier' : '',
                        
                }
        }
    
    return response



# Get status of all scrapping scripts
@app.get("/scripts-status")
async def getScriptStatus():
    try:
        with open('/var/www/html/cron/status.txt') as f:
            data = json.load(f)
            return {"data":data}
    except Exception as e:        
        return {"data":None,"exception":e} 

if __name__ == '__main__':
    uvicorn.run("index:app", host='127.0.0.1', port=8000, log_level="info", reload=True)
    print("running")