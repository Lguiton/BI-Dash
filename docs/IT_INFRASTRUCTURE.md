# IT infrastructure labs (IT Technician, part 2)

Where: **IT tools > Infrastructure labs**. Code: `backend/app/services/it_infra.py`, `it_ops.py`, `routers/infra.py`; tests: `backend/tests/test_infra.py`.

## What was built

| Tool | What it does |
|---|---|
| Group Policy resolver | Which setting wins: Local, Site, Domain, OUs; link order, Enforced, Block Inheritance, security filtering, WMI pass/fail |
| LDIF checker and builder | Required attributes, RDN match, duplicate DNs, missing parents, plain-text passwords; builds user, group and OU entries |
| RBAC audit | Undefined roles, inheritance loops, wide roles, direct grants, separation-of-duties conflicts |
| RAID rebuild risk | Chance of a read error or second failure during a rebuild (levels 0, 1, 5, 6, 10) |
| Backup planner | Full vs incremental vs differential: storage, restore chain, restore time, RPO and RTO |
| DR check | Per system RPO/RTO, restore tests, 3-2-1 |
| Load balancer simulator | Round robin, weighted, least connections, IP hash, with a failed server |
| HTTP lookup, website triage, access-log summary | Status meanings, DNS to TCP to TLS to HTTP order, scanner probes |
| Checklists | Printing, media sanitisation (NIST 800-88), BYOD, DR test, Group Policy change |
| Cheat sheets | Printing, Directory and LDAP, Group Policy, Web and site triage |

Already in the app and not rebuilt: RAID capacity and availability maths, onboarding/offboarding/disposal checklists, hashing, firewall and port tools.

## Cannot be built here

Real Active Directory, OpenLDAP and Kerberos servers; real RAID controllers; backup software (Veeam, restic); real load balancers; IDS engines (Snort); printers and print servers. Practise these in virtual machines on your own PC.

## Mistakes and dated claims found in the source (15)

1. Hashing: the course says two different inputs should 'never' give the same output. That is impossible (there are more inputs than outputs). A good hash makes finding a collision computationally infeasible; MD5 and SHA-1 fail that test.
2. Passwords: one lesson calls passwords 'the most secure common safeguards'. They are among the weakest single factors; they need length, uniqueness, a manager and a second factor.
3. Disk encryption: it is described as giving confidentiality 'and integrity'. Full-disk encryption protects confidentiality; it does not by itself detect tampering. Secure Boot and measured boot protect the boot chain.
4. 802.1X reading: it lists WPA and WPA2 under 'shared key' methods and then says WPA 'enforces 802.1X'. Only the Enterprise modes use 802.1X; the Personal modes use a shared passphrase.
5. TACACS+ is called an 'open standard released in 1993'. TACACS+ stayed Cisco-originated; it was published as informational RFC 8907 in 2020. The 1993 date belongs to the older TACACS (RFC 1492).
6. WEP: the lesson says never to send plaintext and ciphertext together, but the real flaw is the short IV sent in clear with a reused RC4 key stream. Also 'roughly 5,000 packets until an IV repeats' is a birthday-bound estimate, not a guarantee.
7. AES: 'the first and only public cipher approved for top secret information' is an unsourced absolute and dated. Check NSA's current CNSA suite.
8. Counter-based tokens are called more secure than time-based ones for 'two reasons'. TOTP is the common standard and HOTP's weakness is counter drift; neither stops real-time phishing, which security keys (FIDO) do.
9. Mobile and Wi-Fi coverage stops at WPA2: WPA3 and SAE are not mentioned, which makes it dated.
10. Data destruction: 'low-level formatting' with consumer tools is described as a way to zero a drive. Modern drives cannot be low-level formatted outside the factory (zero-fill is an overwrite), multiple passes are not needed on modern drives (NIST SP 800-88 says one), and SSDs need a secure-erase or cryptographic-erase command, not overwriting. Degaussing does not work on SSDs or flash.
11. FISMA is described as requiring data to be stored on US soil. FISMA itself does not say that; location rules come from agency policy and programs such as FedRAMP.
12. Load balancers: 'Classic', 'Application', 'Network' and 'Gateway' load balancers are Amazon Web Services product names presented as general types, and the claim that an application load balancer guards against DDoS overstates it (that needs a WAF or DDoS service).
13. Backups: incremental is defined as backing up 'only the data that's changed in files'. Incremental backs up what changed since the LAST backup of any kind, usually at file level; block-level change tracking is a separate feature.
14. Group Policy lesson: precedence is explained as site, domain, OU, but the Local policy (applied first) and the Enforced and Block Inheritance options that can reverse the order are left out of that lesson.
15. The document is pasted web pages (Wikipedia articles on RBAC, LDIF, RAID and HTTP status codes, a Microsoft documentation set) with menu text, 'needs more citations' banners and some sections repeated (LDIF twice, glossaries repeated). Treat those as reference dumps, not course text.

All numbers from the simulators are models, not measurements of your hardware.
