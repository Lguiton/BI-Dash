REAL-WORK TEST FILES (all made-up; "Sample Co" is not a real business; IP addresses are from documentation ranges)

One file per field, each in a different format. Use them in the Real workspace to rehearse a job
end to end. Delete the test rows/tables afterward (or practise in Practice first). Do not share any
of this as real client work.

File                                  Field          Upload where                         What to look for
01_analyst_orders.csv                 Analyst        My data, then Data quality            2 duplicate order ids, 3 blank qty, 1 negative qty, 1 impossible date (2026-13-05). Margin = total profit / total revenue.
02_scientist_ab_test.xlsx             Data Scientist My data (sheet "Results")             Control ~9% vs variant ~11% conversion. Is it real? Sample size, interval, what you would NOT claim.
03_ml_churn_training.json             ML             My data                               Predict "churned". Beat the baseline; split fairly; check leakage.
04_engineering_events_raw.tsv         Data Eng       Data Intake                           A blank user, a bad timestamp, a duplicate event id, a negative amount: should go to quarantine.
05_ai_returns_policy.docx             AI             Any upload button on the AI page      Policy text plus 5 test questions with answers (one is NOT covered: the right answer is "I don't know").
06_pm_backlog_semicolon.csv           Project mgmt   My data (semicolon separator)         8 tasks with dates MM/DD/YYYY: critical path, risk, slip. Estimate for T06 is stored as text.
07_sysanalyst_interview_notes.pdf     Sys Analyst    Upload on the Systems Analyst page    Turn the notes into testable requirements; list the open questions.
08_fullstack_openapi.json             Full Stack     OpenAPI lint (Pro lab, paste or upload) DELETE endpoint with no auth or summary; thin schemas.
09_security_auth.log                  Cybersecurity  Log analysis                          40 failed logins then a success from 203.0.113.50, then a sudo read of /etc/shadow. Expect a critical finding.
10_network_capture.pcap               Network        Capture file reader                   Normal DNS and HTTPS from 192.0.2.20, plus a port scan from 203.0.113.77.
11_itsupport_work_order_scan.png      IT repair      Any upload button (needs OCR: launcher choice 1 / WSL)  A photographed work order. Check the OCR against the picture: total should be $244.50.
12_cpe_can_log.txt                    Computer Eng   CAN signals tool (paste a frame and the 3 signal lines at the top)  Last frame decodes to ~1960 rpm, 69 C, 34 %.
