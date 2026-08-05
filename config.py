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
    {"name": "Mizrahi Tefahot","url": "https://www.mizrahi-tefahot.co.il/about-mizrahi-tefahot-he/career/open-jobs/",},
    {
        "name": "Tel Aviv Hunter HRMS",
        "url": "https://telaviv-ext.hunterhrms.com/category?cid=45",
        "engine": "hunter_hrms_api",
        "category_id": 45,
    },
    {"name": "TASMC (Ichilov)", "url": "https://www.tasmc.org.il/career/doctors-careers/"},
    {"name": "Ramat Gan Municipality", "url": "https://www.ramat-gan.muni.il/michrazim-and-jobs-lobby/"},
    {"name": "Altshuler Shaham", "url": "https://careers.topmatch.co.il/AltshulerShaham/"},
    {"name": "Tikal", "url": "https://www.tikalk.com/career/"},
    {"name": "Nvidia", "url": "https://jobs.nvidia.com/careers?start=0&pid=893396838168&sort_by=timestamp"},
    {"name": "Microsoft", "url": "https://careers.microsoft.com/v2/global/en/locations/israel.html"},
    {"name": "SAP", "url": "https://jobs.sap.com/go/SAP-Jobs-in-Israel/851401/"},
    {"name": "Palo Alto", "url": "https://jobs.paloaltonetworks.com/en/location/israel-jobs/47263/294640/2"},
    {
        # salesforce.com itself is behind a WAF that blocks headless
        # browsers outright; the real listings live on Salesforce's Workday
        # external career site instead.
        "name": "Salesforce",
        "url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site",
        "engine": "workday",
    },
    {"name": "Cyberark Software", "url": "https://jobs.paloaltonetworks.com/en/search-jobs/Israel/47263/2/294640/31x5/34x75/50/2"},
    {"name": "Panaya", "url": "https://www.panaya.com/careers/#b-career-listing-1"},
    {"name": "Autodesk Israel", "url": "https://autodesk.wd1.myworkdayjobs.com/Ext"},
    {"name": "Cyera", "url": "https://www.cyera.com/careers-il#open-positions"},
    {"name": "AppsFlyer", "url": "https://careers.appsflyer.com/#careersOps"},
    {"name": "Overwolf ", "url": "https://careers.overwolf.com/#position"},
    {
        # rubrik.com is behind a WAF too; listings actually live on Greenhouse.
        "name": "Rubrik",
        "url": "https://www.rubrik.com/company/careers#departments",
        "engine": "greenhouse_api",
        "board_token": "rubrik",
    },
    {"name": "WSC Sports", "url": "https://wsc-sports.com/careers/"},
    {"name": "Taboola", "url": "https://www.taboola.com/careers/jobs#team=&location=18982"},
    {"name": "Natural Intelligence", "url": "https://www.naturalint.com/?pagename=jobs&comeet_cat=tel-aviv&comeet_all=4B&rd"},
    {"name": "Google Israel", "url": "https://www.google.com/about/careers/applications/jobs/results"},
    {"name": "ServiceNow", "url": "https://careers.servicenow.com/locations/emea/israel/"},
    {"name": "Meta", "url": "https://www.metacareers.com/tel-avivjobsearch/"},
    {"name": "Thales Cyber Security Products-Imperva", "url": "https://careers.thalesgroup.com/global/en/search-results"},
    {"name": "Amazon Israel", "url": "https://www.amazon.jobs/content/en/locations/israel/tel-aviv"},
    {"name": "Akamai Technologies", "url": "https://jobs.akamai.com/en/sites/CX_1/jobs?location=Israel&locationId=300000000469279&locationLevel=country&mode=location"},
    {"name": "LSports", "url": "https://www.lsports.eu/careers/"},
    {"name": "Apple Israel", "url": "https://jobs.apple.com/en-il/search?location=israel-ISR&page=2"},
    {
        # the rendered page occasionally trips Greenhouse's bot-check;
        # calling the public board API directly is more reliable.
        "name": "mavens by Zynga",
        "url": "https://job-boards.greenhouse.io/mavenscareers",
        "engine": "greenhouse_api",
        "board_token": "mavenscareers",
    },
    {"name": "Semperis", "url": "https://www.semperis.com/careers/"},
    {"name": "Intel", "url": "https://intel.wd1.myworkdayjobs.com/External"},
    {"name": "Remitly Israel", "url": "https://careers.remitly.com/job-search-results/"},
    {"name": "Lemonade", "url": "https://makers.lemonade.com/"},
    {"name": "Innovid", "url": "https://job-boards.greenhouse.io/innovid#.WqbBOxPwZhA"},
    {"name": "Aidoc", "url": "https://www.aidoc.com/about/careers/#positions"},
    {"name": "BigID", "url": "https://bigid.com/company/careers/#job-board"},
    {"name": "eToro", "url": "https://www.etoro.com/about/careers/#join-our-team"},
    {"name": "Varonis Systems ", "url": "https://careers.varonis.com/", "engine": "varonis_api"},
    {"name": "Riskified", "url": "https://www.riskified.com/careers/#positions"},
    {"name": "NICE", "url": "https://www.nice.com/careers/apply"},
    {
        "name": "Verint",
        "url": "https://fa-epcb-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/jobs?mode=location",
        "engine": "oracle_hcm_api",
        "site_number": "CX",
    },
    {"name": "Orca Security ", "url": "https://orca.security/about/careers/#open-positions"},
    {"name": "Pluri Biotech ", "url": "https://www.linkedin.com/company/pluri-biotech/jobs/"},
    {"name": "Coralogix", "url": "https://coralogix.com/careers/#comeet-jobs"},
    {"name": "Optibus", "url": "https://optibus.com/company/careers/jobs/"},
    {"name": "Glassbox ", "url": "https://www.glassbox.com/careers/roles/"},
    {"name": "Digital Turbine", "url": "https://digitalturbine.wd501.myworkdayjobs.com/Digital_Turbine_External_Careers"},
    {"name": "OPTIMOVE", "url": "https://www.optimove.com/careers#current-openings"},
    {"name": "Check Point Software Technologies ", "url": "https://careers.checkpoint.com/index.php?m=cpcareers&a=search&_gl=1*1gxg2o4*_gcl_au*MjA3Mzg3ODcwLjE3ODU3NjI1Mjc."},
    {"name": "AERONAUTICS", "url": "https://career.aeronautics-sys.com/open-positions/?department=5768ac99528b44c6bd972c70d06c43d6"},
    {"name": "Priority Software", "url": "https://www.priority-software.com/careers/"},
    {"name": "Guesty", "url": "https://www.guesty.com/careers/"},
]

# Compatibility keyword sets (English + Hebrew). A candidate job title/snippet
# is scored against these three categories.
KEYWORDS = {
    "role": [
        "developer", "software engineer", "programmer", "full stack",
        "fullstack", "backend", "back-end",
        "engineer", "coder",
        "מתכנת", "מתכנת/ת", "מתכנתת", "מפתח", "מפתח/ת", "מפתחת",
        "תוכניתן", "תוכניתן/ית", "תוכניתנית", "הנדסת תוכנה", "פיתוח תוכנה",
    ],
    "level_junior": [
        "junior", "jr.", "jr ", "entry level", "entry-level", "graduate",
        "new grad", "no experience required", "0-1 year", "0-2 years",
        "ג'וניור", "ג׳וניור", "גיוניור", "ללא ניסיון",
        "התחלת קריירה", "כניסה להייטק",
    ],
    # Explicit signal that a posting is NOT junior. Presence of any of these
    # disqualifies the job outright, regardless of how well role/location match.
    "level_senior": [
        "senior", "sr.", "sr ", "sr)", "mid-level", "mid level", "middle level",
        "team lead", "tech lead", "lead developer", "staff ", "staff-",
        "principal ", "principal-", "5+ years", "7+ years", "10+ years",
        "lead","director",
        "בכיר", "בכירה", "ראש צוות", "מוביל/ת צוות", "מוביל צוות",
        "ניסיון של 5", "ניסיון של 7", "מנהל/ת צוות",
    ],
    "location": [
        "israel", "tel aviv", "gush dan", "central israel", "center district",
        "ramat gan", "herzliya", "petah tikva", "petach tikva", "raanana",
        "ra'anana", "kfar saba", "givatayim", "bnei brak", "rishon lezion",
        "rishon le zion",
        "ישראל", "תל אביב", "גוש דן", "מרכז", "רמת גן", "הרצליה", "פתח תקווה",
        "גבעתיים", "בני ברק", "ראשון לציון", "רעננה", "כפר סבא",
    ],
    # Explicit signal that a posting is located somewhere other than Israel.
    # Not exhaustive -- just the countries/hubs global job boards actually
    # use in practice -- but it's a real disqualifier: if a job says
    # "Bangalore, India" it should never show up as compatible just because
    # role matched and no Israeli location happened to be mentioned too.
    "location_foreign": [
        "united states", "usa", "u.s.", "canada", "mexico", "brazil",
        "colombia", "argentina", "chile", "united kingdom", "ireland",
        "france", "germany", "netherlands", "belgium", "spain", "portugal",
        "italy", "switzerland", "austria", "sweden", "norway", "denmark",
        "finland", "poland", "czech republic", "czechia", "hungary",
        "romania", "bulgaria", "greece", "cyprus", "estonia", "latvia",
        "lithuania", "ukraine", "russia", "turkey", "uae",
        "united arab emirates", "saudi arabia", "egypt", "south africa",
        "india", "china", "japan", "south korea", "taiwan", "singapore",
        "malaysia", "indonesia", "philippines", "thailand", "vietnam",
        "australia", "new zealand", "norway"
        # foreign cities that show up without an accompanying country name
        "taipei", "hsinchu", "shanghai", "shenzhen", "bengaluru",
        "bangalore", "pune", "gurugram", "gurgaon", "hyderabad", "manila",
        "alkmaar", "berlin", "düsseldorf", "dusseldorf", "london",
        "southampton", "sydney", "ostrava", "prague", "limassol", "lisbon",
        "kyiv", "seattle", "atlanta", "san francisco", "new york", "denver",
        "dallas", "raleigh", "columbus", "chicago", "boston", "austin",
        "los angeles", "sandy, ut", "vancouver", "toronto", "krakow", "krakw",
        "oslo",
    ],
}

# Weights per category. role alone already clears the 75% bar (85%), since
# most scraped titles don't mention location or level at all -- that info
# often only lives on the full posting page, not the link text. Missing
# location/level is treated as "unknown", not "no match", so it shouldn't
# tank the score; location and level are bonuses on top for when they ARE
# mentioned and match. An explicit senior/mid-level signal (level_senior)
# still disqualifies the job outright, overriding the score.
WEIGHTS = {"role": 85, "level": 5, "location": 10}
COMPATIBILITY_THRESHOLD = 75

STORAGE_PATH = "data/seen_jobs.json"
REPORTS_DIR = "reports"
