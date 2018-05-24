# Cameron Hudson
# 2018-05-23

import os
import re
import time

import bs4
import pickle
import requests
from bs4 import BeautifulSoup

# Constants
RESULTSPERPAGE = 50

# Search parameters
criteria = {"termsAll": ["software engineering"],
            "phrasesExact": [""],
            "termsAny": [""],
            "termsExcluded": ["phd"],
            "titleWords": [""],
            "companies": [""],
            "jobTypes": ["fulltime"],
            "staffingAgenciesOk": [""],
            "salaries": [""],
            "radii": [0],
            "locations": ["California"],
            "ages": ["any"],
            "filter": [0],
            "sortParam": ["date"]}

# Replace all spaces so that the search terms can be used in a URL.
for criterion in criteria:
    for element in criteria[criterion]:
        if isinstance(element, str):
            criteria[criterion] = [element.replace(" ", "+")]

# Build Indeed search URL.
indeedUrlParts = [
    "https://www.indeed.com/jobs?",
    "as_and=" + str(criteria["termsAll"][0]),
    "as_phr=" + str(criteria["phrasesExact"][0]),
    "as_any=" + str(criteria["termsAny"][0]),
    "as_not=" + str(criteria["termsExcluded"][0]),
    "as_ttl=" + str(criteria["titleWords"][0]),
    "as_cmp=" + str(criteria["companies"][0]),
    "jt=" + str(criteria["jobTypes"][0]),
    "st=" + str(criteria["staffingAgenciesOk"][0]),
    "salary=" + str(criteria["salaries"][0]),
    "radius=" + str(criteria["radii"][0]),
    "l=" + str(criteria["locations"][0]),
    "fromage=" + str(criteria["ages"][0]),
    "limit=" + str(RESULTSPERPAGE),
    "filter=" + str(criteria["filter"][0]),
    "sort=" + str(criteria["sortParam"][0]),
    "psf=advsrch"
]

indeedBaseUrl = "&".join(indeedUrlParts)
print("URL used = " + indeedBaseUrl + "&start=0")

"""Return a BeautifulSoup object from the given URL.

url The URL whose source code to request.
return The created BeautifulSoup object.
"""


def getSoupFromUrl(url):
    # time.sleep(0.5)
    page = requests.get(url)
    return BeautifulSoup(page.text, "html.parser")


# Identify number of Indeed results.
soup = getSoupFromUrl(indeedBaseUrl)
searchCount = soup.find("div", attrs={"id": "searchCount"})
searchCount = searchCount.get_text().split()[3]
searchCount = int(searchCount.replace(",", ""))

# Initialize data storage objects.
results = set()
allWords = {}
courseListings = []
jobListings = []

"""Return word counts from paragraph.

paragraph The paragraph to scan.
return A dictionary with words as keys and values as counts.
"""


def getWordCount(paragraph):
    wordCounts = {}
    wordArray = re.split('[^a-zA-Z]', paragraph)
    for word in wordArray:
        word = str(word).lower().rstrip("s")
        if word in allWords:
            allWords[word] += 1
            if word in wordCounts:
                wordCounts[word] += 1
            else:
                wordCounts[word] = 1
        else:
            allWords[word] = 1
            wordCounts[word] = 1

    return wordCounts


# Crawl Indeed.
jobUrls = 0

# Indeed only reports up to 20 pages of results.
searchCount = min([searchCount, 20 * RESULTSPERPAGE])

# Read the pages in reverse order. For large searches,
# newer listings can be inserted on page 0 as the search
# proceeds, shifting listings toward page n.
# Reading backwards misses some listings, but nevertheless
# captures more than reading reading forward and discarding
# listings that we already saw on the previous pages.
for start in reversed(range(0, searchCount, RESULTSPERPAGE)):
    indeedUrl = indeedBaseUrl + "&start=" + str(start)
    soup = getSoupFromUrl(indeedUrl)
    organicJobSoup = soup.find_all(
        "div", attrs={"data-tn-component": "organicJob"})
    for organicJob in organicJobSoup:
        # if organicJob.a["href"] in results:
        #     print("Already saw " + "https://www.indeed.com" + organicJob.a["href"])
        results.add(organicJob.a["href"])
    jobUrls += len(organicJobSoup)
    print("Number of job URLs saved = " + str(jobUrls) + " of " +
          str(searchCount) + " (" + str(len(results)) + " unique," +
          "URL = " + indeedUrl + " .")

"""Perform an HTTP request and return a soup object if successful.

link The URL of the page to request
return A soup object if successful, False otherwise.
"""


def attemptToRetrievePage(link):
    try:
        soup = getSoupFromUrl(link)
        if "indeed" in link:
            soup.find("b", attrs={"class": "jobtitle"}).get_text()
        elif "cmu" in link:
            soup.find_all("h2")[1].get_text()
        else:
            print("Error! Found neither \"indeed\" nor \"cmu\" in link!")
        return soup
    except:
        return False


"""Return an array containing the salary estimate or range.

salaryTag The HTML tag containing the salary data.
return An array of salary data.
"""


def parseSalary(salaryTag):
    if salaryTag == None:
        return [0]
    else:
        salary = [int(s.replace(",", "")) for s in re.split(
            r"[^0-9,]+", salaryTag.get_text()) if (len(s) > 0)]
    if salary[0] < 1000:

        # The salary is reported as an hourly rate. Convert it to an annual salary.
        for entry in salary:
            entry *= 52 * 40

    return salary


"""Extract data from the Indeed job listing page.

link The URL of the Indeed job listing page
"""


def processIndeedPage(link):
    soup = False
    while not soup:
        soup = attemptToRetrievePage(link)
    listing = {}
    listing["link"] = link
    listing["title"] = soup.find("b", attrs={"class": "jobtitle"}).get_text()
    listing["company"] = soup.find(
        "span", attrs={"class": "company"}).get_text()
    summary = soup.find("span", attrs={"id": "job_summary"}).get_text()
    salaryTag = soup.find(name="span", attrs={
                          "class": "no-wrap"}, string=re.compile(r"\$[0-9,]+"))
    listing["salary"] = parseSalary(salaryTag)
    listing["summaryWords"] = getWordCount(summary)
    listing["titleWords"] = getWordCount(listing["title"])
    jobListings.append(listing)


# Visit each Indeed job listing page pull data.
for result in results:
    print("Processing job listing " + str(1 + len(jobListings)) +
          " of " + str(len(results)) + " ...")
    processIndeedPage("https://www.indeed.com" + result)

"""Process CMU course data.

link The URL of the course page.
"""


def processCmuPage(link):
    soup = False
    while not soup:
        soup = attemptToRetrievePage(link)
    listing = {}
    listing["link"] = link
    listing["title"] = soup.find_all("h2")[1].get_text()
    listing["salary"] = [0]
    summary = soup.find("p").get_text()
    listing["summaryWords"] = getWordCount(summary)
    listing["titleWords"] = getWordCount(listing["title"])
    courseListings.append(listing)


# Crawl CMU course list.
cmuUrl = "http://www.ece.cmu.edu/courses/index.html"
soup = getSoupFromUrl(cmuUrl)
links = set()
for td in soup.find_all("td"):
    if td.a != None:
        links.add(td.a["href"])
for link in links:
    processCmuPage("http://www.ece.cmu.edu/courses/" + link)
    print("Processing course listing " + str(len(courseListings)) +
          " of " + str(len(links)) + " ...")

# Save the data so we don't have to scrape it again (unless we want to).
pickle.dump(allWords, open("allWords.p", "wb"))
pickle.dump(jobListings, open("jobListings.p", "wb"))
pickle.dump(courseListings, open("courseListings.p", "wb"))

print("Done.")
