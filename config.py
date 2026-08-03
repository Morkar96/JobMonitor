"""
Configuration for the job monitor.

Each site entry:
  name      - friendly label used in reports / storage keys
  url       - the page to scrape
  engine    - "workday" uses the Workday-specific extractor,
              "generic" uses the generic link-scraper (default)
  wait_selector - optional CSS selector to wait for before scraping
                  (useful for slow-loading SPAs). None = just wait for
                  network idle.
"""

SITES = [
    {"name": "HiBob", "url": "https://www.hibob.com/careers/"},
    {"name": "Essence Group", "url": "https://www.essence-grp.com/jobs/"},
    {"name": "Silverfort", "url": "https://www.silverfort.com/careers/#jobs"},
    {"name": "Intuit Israel", "url": "https://jobs.intuit.com/location/israel-jobs/27595/294640/2/"},
    {
        "name": "Cadence",
        "url": "https://cadence.wd1.myworkdayjobs.com/External_Careers?Location_Country=084562884af243748dad7c84c304d89a",
        "engine": "workday",
    },
    {"name": "Candex", "url": "https://www.candex.com/careers"},
    {"name": "Happly AI", "url": "https://happlyai.com/jobs"},
    {
        "name": "80K (EightyK)",
        "url": "https://eightyk.co.il/jobs?seniorityLevel=junior",
    },
    {
        "name": "Malam Mertens",
        "url": "https://mertens.malam.com/%d7%a8%d7%a9%d7%99%d7%9e%d7%aa-%d7%9e%d7%a9%d7%a8%d7%95%d7%aa-%d7%a8%d7%92%d7%99%d7%9c/?prof=9&loc=40&t=",
    },
    {
        "name": "Adam Total (Harel)",
        "url": "https://career.adamtotal.co.il/?token=6675d401-0dee-428a-a776-5d41885d16b0-harel",
    },
    {"name": "Phoenix (fnx)", "url": "https://www.fnx.co.il/career/open-positions/"},
    {"name": "Migdal", "url": "https://my.migdal.co.il/about/jobs"},
    {"name": "Clal Insurance", "url": "https://www.clalbit.co.il/careers/"},
    {"name": "555", "url": "https://www.555.co.il/about/career.html"},
    {"name": "Meitav", "url": "https://careers.topmatch.co.il/Meitav/"},
    {"name": "Bank Hapoalim", "url": "https://www.bankhapoalim.co.il/he/jobs-site/lobby"},
    {"name": "More Invest", "url": "https://careers.topmatch.co.il/MoreInvest/"},
    {"name": "Bank Leumi", "url": "https://www.leumi.co.il/leumi_main/searchjobs"},
    {"name": "FIBI", "url": "https://www.fibi.co.il/private/general/about/jobs/jobsfibi/"},
    {"name": "FIBI Mataf", "url": "https://www.fibi.co.il/private/general/about/jobs/jobsmataf/"},
    {
        "name": "Mizrahi Tefahot",
        "url": "https://www.mizrahi-tefahot.co.il/about-mizrahi-tefahot-he/career/open-jobs/",
    },
    {"name": "Tel Aviv Hunter HRMS", "url": "https://telaviv-ext.hunterhrms.com/category?cid=45"},
    {"name": "TASMC (Ichilov)", "url": "https://www.tasmc.org.il/career/doctors-careers/"},
    {"name": "Ramat Gan Municipality", "url": "https://www.ramat-gan.muni.il/michrazim-and-jobs-lobby/"},
    {"name": "Altshuler Shaham", "url": "https://careers.topmatch.co.il/AltshulerShaham/"},
    {"name": "Tikal", "url": "https://www.tikalk.com/career/"},
    {"name": "Nvidia", "url": "https://jobs.nvidia.com/careers?start=0&pid=893396838168&sort_by=timestamp"},
    {"name": "Microsoft", "url": "https://careers.microsoft.com/v2/global/en/locations/israel.html"},
    {"name": "SAP", "url": "https://jobs.sap.com/go/SAP-Jobs-in-Israel/851401/"},
    {"name": "Palo Alto", "url": "https://jobs.paloaltonetworks.com/en/location/israel-jobs/47263/294640/2"},
    {"name": "Salesforce", "url": "https://www.salesforce.com/company/careers/jobs/?search=&country=Israel&pagesize=20&_ga=2.66398318.1528450245.1785758557-435796467.1785758557#results"},
    {"name": "Cyberark Software", "url": "https://jobs.paloaltonetworks.com/en/search-jobs/Israel/47263/2/294640/31x5/34x75/50/2"},
    {"name": "Panaya", "url": "https://www.panaya.com/careers/#b-career-listing-1"},
    {"name": "Autodesk Israel ", "url": "https://autodesk.wd1.myworkdayjobs.com/Ext"},
    {"name": "Cyera", "url": "https://www.cyera.com/careers-il#open-positions"},
    {"name": "AppsFlyer", "url": "https://careers.appsflyer.com/#careersOps"},
    {"name": "Overwolf ", "url": ""},
    {"name": "Rubrik", "url": ""},
    {"name": "WSC Sports", "url": ""},
    {"name": "Taboola", "url": ""},
    {"name": "Natural Intelligence", "url": ""},
    {"name": "Google Israel", "url": ""},
    {"name": "ServiceNow", "url": ""},
    {"name": "Meta", "url": ""},
    {"name": "Thales Cyber Security Products-Imperva", "url": ""},
    {"name": "Amazon Israel", "url": ""},
    {"name": "Akamai Technologies", "url": ""},
    {"name": "LSports", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
    {"name": "", "url": ""},
]

# Compatibility keyword sets (English + Hebrew). A candidate job title/snippet
# is scored against these three categories.
KEYWORDS = {
    "role": [
        "developer", "software engineer", "programmer", "full stack",
        "fullstack", "frontend", "front-end", "backend", "back-end",
        "engineer", "coder", "swe",
        "מתכנת", "מתכנת/ת", "מתכנתת", "מפתח", "מפתח/ת", "מפתחת",
        "תוכניתן", "תוכניתן/ית", "תוכניתנית", "הנדסת תוכנה", "פיתוח תוכנה",
    ],
    "level": [
        "junior", "jr.", "jr ", "entry level", "entry-level", "graduate",
        "new grad", "no experience required", "0-1 year", "0-2 years",
        "ג'וניור", "ג׳וניור", "גיוניור", "ללא ניסיון", "בוגר/ת", "בוגרי",
        "אקדמאי/ת ללא ניסיון", "סטודנט/ית", "התחלת קריירה", "כניסה להייטק",
    ],
    "location": [
        "tel aviv", "gush dan", "central israel", "center district",
        "ramat gan", "herzliya", "petah tikva", "petach tikva",
        "givatayim", "bnei brak", "rishon lezion", "rishon le zion",
        "תל אביב", "גוש דן", "מרכז", "רמת גן", "הרצליה", "פתח תקווה",
        "גבעתיים", "בני ברק", "ראשון לציון", "רעננה", "כפר סבא",
    ],
}

# Weights per category. role + level together already clear the 75% bar;
# location is a bonus on top.
WEIGHTS = {"role": 40, "level": 40, "location": 20}
COMPATIBILITY_THRESHOLD = 75

STORAGE_PATH = "data/seen_jobs.json"
REPORTS_DIR = "reports"
