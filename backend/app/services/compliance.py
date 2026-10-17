"""Compliance library: plain-language summaries of privacy and security rules, with official links.

These are summaries in our own words, not the legal texts and not legal advice. Each entry links to the
official source; read that before relying on anything. Figures change, so check the date and the source."""
REVIEWED = "2026-10"
NOTE = ("Plain-language summaries, not the legal text and not legal advice. Laws change and apply differently to different "
        "businesses. Use the official link for the exact wording, and ask a lawyer before a contract, a breach or a regulator letter.")

L = {  # shorthand for link builders
    "hhs": "https://www.hhs.gov/hipaa/index.html",
}


def _e(id, name, short, kind, where, applies, covers, duties, penalties, freelancer, links, kw=""):
    return {"id": id, "name": name, "short": short, "kind": kind, "where": where, "applies": applies, "covers": covers,
            "duties": duties, "penalties": penalties, "freelancer": freelancer,
            "links": [{"label": a, "url": b} for a, b in links], "keywords": kw}


LAWS = [
    _e("hipaa", "HIPAA (Privacy, Security and Breach Notification Rules)", "US health information rules", "Federal law (US)", "United States",
       "Covered entities (doctors, dentists, clinics, health plans, clearinghouses) and their business associates, which includes an IT contractor who can access their patient data.",
       "Protected health information (PHI): health data tied to a person, in any form. The Security Rule covers the electronic form (ePHI).",
       ["Risk analysis and safeguards: administrative, physical and technical (access control, unique logins, audit logs, encryption as an addressable control, backups, disposal).",
        "Minimum necessary: touch only the PHI the task needs.",
        "A business associate agreement (BAA) must be signed before a contractor handles PHI.",
        "Breach notification: affected people without unreasonable delay and within 60 days of discovery; HHS and sometimes media depending on size. A business associate tells the covered entity.",
        "A proposed update to the Security Rule has been in the works. Check hhs.gov for its status before assuming anything has changed."],
       "Tiered civil penalties per violation with yearly caps that HHS adjusts for inflation; willful neglect and knowingly misusing PHI can bring criminal penalties.",
       ["Do not take clinic or medical-office jobs that expose patient data without a signed BAA and the right insurance.",
        "Never copy PHI into this tool, an AI prompt, email or your personal devices. Use fake data for practice.",
        "If a repair puts you in front of a screen with patient records, close it, tell the practice manager, and write down that you did."],
       [("HHS HIPAA home", "https://www.hhs.gov/hipaa/index.html"), ("Security Rule summary", "https://www.hhs.gov/hipaa/for-professionals/security/index.html"),
        ("Breach Notification Rule", "https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html"), ("Business associates", "https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/business-associates/index.html"),
        ("Full regulation text (45 CFR Parts 160 and 164)", "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C")], "hipaa phi ephi health medical patient clinic dental baa business associate"),
    _e("gdpr", "GDPR (EU and UK General Data Protection Regulation)", "EU privacy law", "EU regulation", "European Union (the UK has a near-identical UK GDPR)",
       "Anyone who handles personal data of people in the EU, even from outside it, if they offer goods or services to them or monitor their behavior.",
       "Any information that identifies or can identify a person: names, emails, IP addresses, device IDs, location.",
       ["Needs a lawful basis (consent, contract, legitimate interest and others) and a stated purpose.",
        "Data minimization, accuracy, storage limits, security.",
        "People can ask for access, correction, deletion, portability and to object.",
        "Breach: notify the regulator within 72 hours of becoming aware unless unlikely to harm people.",
        "Processors (like an IT contractor) need a written data processing agreement with the controller."],
       "Up to 20 million euros or 4 percent of worldwide annual turnover for the most serious violations; lower tier up to 10 million or 2 percent.",
       ["Rarely applies to a local Henderson job. It can apply if a client sells to EU customers or you store EU people's data.",
        "If a client asks for a data processing agreement, have it reviewed before you sign."],
       [("Official text (EUR-Lex)", "https://eur-lex.europa.eu/eli/reg/2016/679/oj"), ("gdpr-info.eu readable copy", "https://gdpr-info.eu/"), ("European Data Protection Board", "https://www.edpb.europa.eu/")], "gdpr eu europe uk personal data processor controller 72 hours"),
    _e("ccpa", "CCPA and CPRA (California privacy law)", "California consumer privacy", "State law (California)", "California residents' data",
       "For-profit businesses doing business in California that meet one test: gross revenue above an inflation-adjusted threshold (about 25 million dollars at the start), or handle data on 100,000 or more consumers or households, or earn half or more of revenue from selling or sharing personal information.",
       "Personal information about California residents, including browsing data and inferences. Sensitive personal information has extra limits.",
       ["Tell people what you collect and why (notice at collection, privacy policy).",
        "Rights to know, delete, correct, opt out of sale or sharing, and limit use of sensitive data.",
        "Honor opt-out preference signals such as Global Privacy Control.",
        "Service-provider contracts must limit how the vendor uses the data.",
        "Private lawsuits are allowed for certain data breaches caused by weak security."],
       "Civil penalties per violation enforced by the California Attorney General and the California Privacy Protection Agency; statutory damages in breach lawsuits.",
       ["A small local freelancer is likely under the thresholds, but a larger client may ask you to act as its service provider. Read the contract terms on data use."],
       [("California AG CCPA page", "https://oag.ca.gov/privacy/ccpa"), ("California Privacy Protection Agency", "https://cppa.ca.gov/"), ("Statute text", "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5")], "ccpa cpra california consumer privacy opt out sale"),
    _e("ftc-act", "FTC Act Section 5 (unfair or deceptive practices)", "Truth-in-advertising and data promises", "Federal law (US)", "United States",
       "Almost every business. The FTC treats broken privacy or security promises, and unreasonable security, as deceptive or unfair.",
       "Advertising claims, reviews and endorsements, privacy policies, data security practices.",
       ["Do not claim things you cannot back up (certifications, guarantees, results).",
        "Do what your privacy policy and contracts say you do.",
        "Disclose paid or free-product endorsements and never fake reviews.",
        "Keep reasonable security for the data you hold."],
       "Orders, ongoing audits and civil penalties, with consumer refunds in some cases.",
       ["Marketing copy for yourself and clients should state only what is true: do not say HIPAA-compliant, certified or guaranteed unless it is.",
        "Never write fake testimonials. Label practice or sample work as practice."],
       [("FTC privacy and security", "https://www.ftc.gov/business-guidance/privacy-security"), ("Endorsement guides", "https://www.ftc.gov/business-guidance/advertising-marketing/endorsements-influencers-reviews"), ("FTC Act text", "https://www.ftc.gov/legal-library/browse/statutes/federal-trade-commission-act")], "ftc deceptive advertising endorsements reviews unfair"),
    _e("safeguards", "FTC Safeguards Rule (GLBA)", "Security rule for non-bank financial businesses", "Federal rule (US)", "United States",
       "Non-bank financial institutions: tax preparers, mortgage brokers, auto dealers, collection agencies, and others that handle customer financial information. Also reaches their service providers.",
       "Nonpublic personal financial information of customers.",
       ["Written information security program with a named Qualified Individual.",
        "Risk assessment, access controls, encryption, multi-factor authentication, logging, secure disposal, staff training, vendor oversight, incident response plan.",
        "Report to the FTC within 30 days of discovery when unencrypted information of 500 or more consumers is taken."],
       "FTC enforcement actions and civil penalties. Smaller institutions get some reduced written-plan requirements.",
       ["If you work for a tax office, accountant, or loan or dealership office, expect them to ask how you protect their customer data."],
       [("FTC Safeguards Rule guide", "https://www.ftc.gov/business-guidance/resources/ftc-safeguards-rule-what-your-business-needs-know"), ("Rule text (16 CFR 314)", "https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-314")], "safeguards glba financial tax preparer dealership mortgage"),
    _e("glba", "GLBA (Gramm-Leach-Bliley Act)", "Privacy and security for financial institutions", "Federal law (US)", "United States",
       "Banks, lenders, insurers, brokers and other financial firms; the FTC enforces it for non-banks.",
       "Customers' nonpublic personal information.",
       ["Give customers a privacy notice and an opt-out for sharing with third parties.",
        "Protect the data with the Safeguards Rule.",
        "No pretexting: do not get financial information under false pretenses."],
       "Enforced by the FTC and banking regulators; penalties vary by agency.",
       ["Treat anything you see in a financial office as confidential and do not copy it."],
       [("FTC GLBA guide", "https://www.ftc.gov/business-guidance/privacy-security/gramm-leach-bliley-act")], "glba financial privacy pretexting"),
    _e("pci", "PCI DSS (payment card security standard)", "Card payment security", "Industry standard (contractual)", "Worldwide",
       "Anyone who stores, processes or transmits payment card data. It is enforced by card brands and your payment processor through contracts, not by a government.",
       "Cardholder data and sensitive authentication data.",
       ["Build and maintain a secure network, protect stored cardholder data, keep systems patched, restrict access by need to know, use unique IDs and multi-factor authentication, log and test, keep a security policy.",
        "Never store the full magnetic stripe data, card verification code or PIN after authorization.",
        "Smaller merchants usually complete a self-assessment questionnaire; using a hosted payment page shrinks scope."],
       "Fines and higher processing fees from the processor, and loss of the ability to take cards; plus breach costs.",
       ["Never write down or store a client's card numbers while fixing a point-of-sale system.",
        "Keep client payments on a processor's hosted page rather than your own systems."],
       [("PCI Security Standards Council", "https://www.pcisecuritystandards.org/"), ("Small merchant resources", "https://www.pcisecuritystandards.org/merchants/")], "pci dss card payment merchant point of sale pos"),
    _e("canspam", "CAN-SPAM Act", "Commercial email rules", "Federal law (US)", "United States",
       "Any commercial email, including to business contacts.",
       "Messages whose main purpose is advertising or promoting a product or service.",
       ["Accurate From, Reply-To and subject lines.", "Say it is an ad when it is one.", "Include your valid physical postal address.",
        "A clear opt-out; honor it within 10 business days and do not sell the address.", "You are responsible for what others send for you."],
       "Civil penalty of more than 50,000 dollars per email, adjusted yearly.",
       ["Every outreach email needs your real name, address and an unsubscribe line. This tool only drafts; you send it yourself."],
       [("FTC CAN-SPAM guide", "https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business"), ("Statute", "https://www.ftc.gov/legal-library/browse/statutes/controlling-assault-non-solicited-pornography-marketing-act-2003-can-spam-act")], "can-spam email marketing unsubscribe outreach"),
    _e("tcpa", "TCPA (Telephone Consumer Protection Act) and Do Not Call", "Calls and texts to consumers", "Federal law (US)", "United States",
       "Businesses that call or text consumers for marketing.",
       "Autodialed or prerecorded calls, marketing texts, Do Not Call registry numbers.",
       ["Get written consent before marketing texts or autodialed marketing calls.", "Scrub against the National Do Not Call Registry and your own opt-out list.",
        "Honor stop requests quickly and keep consent records.", "Respect calling-hour limits."],
       "Statutory damages of 500 to 1,500 dollars per call or text in private suits, plus regulator fines.",
       ["Do not mass-text leads from a purchased list. Ask permission and keep the proof."],
       [("FTC Do Not Call", "https://www.ftc.gov/business-guidance/resources/qa-telemarketing-sales-rule"), ("FCC TCPA", "https://www.fcc.gov/general/telemarketing-and-robocalls")], "tcpa text sms robocall do not call marketing"),
    _e("coppa", "COPPA (children's online privacy)", "Under-13 online data", "Federal law (US)", "United States",
       "Websites, apps and services aimed at children under 13, or that know a user is under 13.",
       "Personal information from children under 13, including photos, voice and persistent identifiers.",
       ["Verifiable parental consent before collecting a child's data.", "Clear notice, limited collection and retention, reasonable security."],
       "Civil penalties per violation through the FTC.",
       ["Careful with school or kids-programming jobs: collect nothing from children without the school's and parents' say-so."],
       [("FTC COPPA guide", "https://www.ftc.gov/business-guidance/resources/childrens-online-privacy-protection-rule-six-step-compliance-plan-your-business")], "coppa children kids under 13 school app"),
    _e("ferpa", "FERPA (student education records)", "Student record privacy", "Federal law (US)", "United States",
       "Schools and colleges that receive federal education funds, and contractors acting as school officials.",
       "Education records directly tied to a student.",
       ["Parents or eligible students control disclosure.", "Contractors may only use records for the school's purposes under its direction."],
       "The Department of Education can pull federal funding.",
       ["If you fix a school device, do not browse or copy student files."],
       [("Dept of Education FERPA", "https://studentprivacy.ed.gov/ferpa")], "ferpa school student education records"),
    _e("nrs603a", "Nevada NRS 603A (data security and breach notice)", "Nevada security duty, breach and privacy", "State law (Nevada)", "Nevada residents",
       "Businesses that own or license personal information of Nevada residents, and data collectors. The privacy opt-out provisions apply to website and app operators who sell covered information.",
       "Personal information: a name with Social Security, driver license, account, medical or health insurance numbers and similar data, or a login credential.",
       ["Keep reasonable security measures and encrypt covered data when it leaves your control.",
        "Notify affected Nevadans of a breach in the most expedient time possible, without unreasonable delay.",
        "Operators that sell covered information must honor opt-out requests and post a privacy notice.",
        "Nevada also passed a consumer health data privacy law in 2023 (SB 370), with its own consent and notice rules for health data that is not under HIPAA."],
       "Enforced by the Nevada Attorney General; some provisions allow civil damages.",
       ["This is the state rule most likely to touch your Henderson and Las Vegas clients. Ask what personal data they hold and where."],
       [("NRS Chapter 603A (legislature)", "https://www.leg.state.nv.us/nrs/nrs-603a.html"), ("Nevada AG, privacy", "https://ag.nv.gov/About/Privacy/Privacy/")], "nevada nrs 603a breach notice sb 220 sb 370 health"),
    _e("statebreach", "State breach notification laws (all 50 states)", "Every state has one", "State laws (US)", "Depends on where the affected people live",
       "Whoever holds personal information of that state's residents.",
       "Usually a name plus an identifier such as Social Security, license, financial or medical data.",
       ["Notify affected people, and often the state attorney general, after a breach. Deadlines range from as short as 30 days to no fixed number.",
        "Encrypted data is often exempt if the key was not taken."],
       "Varies by state: fines, state attorney general actions and sometimes private suits.",
       ["If a client has a breach, the first calls are the client and their lawyer. Document facts and times; do not decide notification duties yourself."],
       [("NCSL state breach laws list", "https://www.ncsl.org/technology-and-communication/security-breach-notification-laws")], "breach notification state attorney general"),
    _e("cfaa", "CFAA (Computer Fraud and Abuse Act)", "Authorized access to computers", "Federal law (US)", "United States",
       "Everyone. It makes unauthorized access to computers a crime.",
       "Accessing a computer without authorization or beyond what you are allowed.",
       ["Get written authorization (scope, systems, dates) before any security testing.", "Stay inside the scope you were given."],
       "Criminal penalties and civil claims.",
       ["For security work: written scope first, always. Use your own labs for learning."],
       [("DOJ CFAA overview", "https://www.justice.gov/criminal/criminal-ccips/computer-fraud-and-abuse-act")], "cfaa hacking authorization penetration test scope"),
    _e("sox", "Sarbanes-Oxley (SOX)", "Financial reporting controls", "Federal law (US)", "United States",
       "Public companies and their auditors. IT contractors meet it through access and change-control requirements.",
       "Accuracy of financial reports and the IT controls behind them.",
       ["Controls over who changes financial systems, with logs.", "Records retention and no tampering."],
       "Serious civil and criminal penalties for executives and for altering records.",
       ["For clients that are public companies, follow their change-control process and keep logs."],
       [("SEC SOX resources", "https://www.sec.gov/spotlight/sarbanes-oxley.htm")], "sox sarbanes oxley audit change control"),
    _e("nist", "NIST Cybersecurity Framework 2.0 and ISO 27001", "Security frameworks, not laws", "Voluntary frameworks", "Worldwide",
       "Anyone who wants a recognized structure for security. Clients and contracts often require them.",
       "Govern, identify, protect, detect, respond and recover (NIST CSF 2.0). ISO 27001 is a certifiable management system.",
       ["Use as a checklist to organize risk work and explain it to clients.", "NIST publishes free small-business guides."],
       "None directly. They are used as evidence of reasonable security.",
       ["Good structure for a security assessment write-up and a client security policy."],
       [("NIST CSF 2.0", "https://www.nist.gov/cyberframework"), ("NIST small business", "https://www.nist.gov/itl/smallbusinesscyber"), ("ISO 27001 overview", "https://www.iso.org/standard/27001")], "nist csf iso 27001 framework security policy"),
]

GLOSSARY = [
    {"term": "PII", "meaning": "Personally identifiable information: anything that identifies a person alone or combined, such as name, address, phone, email, Social Security number, license number, IP address, photos."},
    {"term": "Sensitive PII", "meaning": "PII that can cause serious harm if exposed: Social Security, financial account, driver license, passport, biometrics, precise location, login credentials."},
    {"term": "PHI", "meaning": "Protected health information under HIPAA: health, care or payment data tied to a person, held by a covered entity or its business associate."},
    {"term": "ePHI", "meaning": "PHI in electronic form: databases, email, scans, backups, screenshots."},
    {"term": "Covered entity", "meaning": "A healthcare provider, health plan or clearinghouse covered by HIPAA."},
    {"term": "Business associate (BA) and BAA", "meaning": "A contractor who handles PHI for a covered entity. A business associate agreement is the contract that must be signed first."},
    {"term": "Controller and processor", "meaning": "GDPR terms: the controller decides why data is used; the processor handles it for the controller. An IT contractor is usually a processor."},
    {"term": "Data subject", "meaning": "The person the data is about."},
    {"term": "Minimum necessary", "meaning": "Only use or see the data a task actually needs."},
    {"term": "Breach", "meaning": "Unauthorized access, loss or exposure of protected data. The law decides what counts, and notice deadlines start at discovery."},
    {"term": "Encryption at rest and in transit", "meaning": "Scrambling data on disk and while it moves over a network. Many breach laws excuse encrypted data if the key was not taken."},
    {"term": "Least privilege", "meaning": "Give each person and account only the access needed for the job."},
    {"term": "Retention", "meaning": "How long records are kept before secure deletion."},
]

CHECKLIST = [
    "Written scope and authorization before touching systems or data.",
    "Ask first: does this client hold health, financial, student, child or card data?",
    "Sign a BAA (health) or data agreement (other) before access when required.",
    "Never put client personal data into this tool, AI prompts, personal email or cloud notes.",
    "Use the least access you need and log in with your own named account.",
    "Do not copy or keep client data after the job; wipe test copies.",
    "Write down what you touched, when, and what you changed.",
    "If something looks like a breach, stop, tell the client, write the facts, and let them and their lawyer decide notices.",
    "Do not promise compliance or certification you do not hold.",
    "Carry the right insurance and ask a lawyer to review contracts.",
]


def _brief(e):
    return {k: e[k] for k in ("id", "name", "short", "kind", "where")}


def library():
    return {"reviewed": REVIEWED, "note": NOTE, "laws": [_brief(e) for e in LAWS], "glossary": GLOSSARY, "checklist": CHECKLIST}


def get(id):
    for e in LAWS:
        if e["id"] == id:
            return {**e, "reviewed": REVIEWED, "note": NOTE}
    return None


def search(q, limit=5):
    toks = [t for t in "".join(c.lower() if c.isalnum() else " " for c in (q or "")).split() if len(t) > 1]
    if not toks:
        return {"results": []}
    scored = []
    for e in LAWS:
        hay_name = (e["name"] + " " + e["short"] + " " + e["keywords"]).lower()
        hay = hay_name + " " + e["applies"].lower() + " " + e["covers"].lower() + " " + " ".join(e["duties"]).lower()
        s = sum(3 for t in toks if t in hay_name) + sum(1 for t in toks if t in hay)
        if s:
            scored.append((s, e))
    scored.sort(key=lambda x: -x[0])
    out = [{**_brief(e), "score": s} for s, e in scored[:limit]]
    gl = [g for g in GLOSSARY if any(t in (g["term"] + " " + g["meaning"]).lower() for t in toks)][:3]
    return {"results": out, "glossary": gl}
