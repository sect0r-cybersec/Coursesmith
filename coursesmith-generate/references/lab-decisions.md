# Lab decision rules

When generating a chapter, decide what kind of lab (if any) the chapter warrants. The point is to set the user up to do the work, not to do it for them.

## Decision flow

1. **Does the chapter have hands-on technical content?** If no, skip lab generation entirely. Conceptual chapters get a single line in the chapter intro: "Conceptual chapter, no hands-on lab."

2. **What's the dominant content type?**

| Source content | Lab type | Output file |
|---|---|---|
| Python with progressive examples | `jupyter` | `lab.ipynb` |
| Shell / bash / CLI tools | `shell` | `lab-guide.md` (+ optional Dockerfile) |
| PowerShell on Windows | `windows` | `lab-guide.md` |
| Active Directory, Sysmon, Defender, Windows internals | `windows` | `lab-guide.md` |
| Networking, routers, switches, firewalls | `network` | `lab-guide.md` |
| Pentesting, web app testing, exploitation | `pentest` | `lab-guide.md` |
| Mixed (e.g. Python script that talks to Windows machine) | go with the dominant *interactive* element | usually `lab-guide.md` |

3. **For mixed labs**, default to `lab-guide.md`. A markdown guide is more flexible than a notebook when the work spans multiple environments.

## Per lab-type guidance

### Jupyter (Python)

Use when:
- Chapter has Python code that builds up logically across the chapter
- Each step's output feeds into the next
- The user benefits from running cells inline and seeing intermediate state

Don't use when:
- Code is just illustrative snippets, not a connected workflow
- Code requires root, network sockets, or other things awkward in Jupyter
- The chapter's primary tool isn't Python

Notebook structure:
- Markdown cell with chapter context and lab overview
- Imports cell
- For each major step in the chapter:
  - Markdown explanation (what this step does, *why*)
  - Code cell with the actual code
  - Markdown follow-up: "Try it" suggestion + common pitfalls
- Final stretch-goals markdown cell

Don't put quiz questions in the notebook. Quizzes belong on the chapter HTML page.

### Shell / bash

Use for:
- Linux command-line work
- CLI tools (curl, jq, nmap, gobuster, etc.)
- Build chains, package management, system admin

Lab guide should include:
- Required tools list with install commands for Debian/Ubuntu and RHEL/Fedora
- Optional Dockerfile if the environment is non-trivial (multiple tools, specific versions)
- Step-by-step commands with expected output excerpts
- "Verify" subsections after each step
- Reminder about safe networks (pentesting tools should never be aimed at networks the user doesn't own)

### Windows / Active Directory

Use for:
- AD enumeration, attacks, defence
- Windows event logs, Sysmon configuration
- PowerShell-heavy chapters
- Defender, AppLocker, WDAC

Lab guide should include:
- VM specs: typically 4 GB RAM minimum per Windows Server, 8 GB if running multiple VMs
- Windows Server eval ISO link: Microsoft Evaluation Center (https://www.microsoft.com/en-us/evalcenter/)
- Windows 10/11 eval ISO (90 days): Microsoft Evaluation Center
- Hypervisor suggestion (Hyper-V, VMware Workstation Player, VirtualBox)
- Network topology (e.g. "isolated host-only network, DC at 192.168.56.10, workstation at 192.168.56.20")
- Roles to install (AD DS, DNS)
- Specific feature flags or audit policies the chapter requires
- A note that the user should never join their lab DC to their home network

### Network

Use for:
- Routing, switching, firewall configuration
- Protocol analysis labs (Wireshark)
- Multi-device network design

Lab guide should include:
- Topology diagram description (textual)
- GNS3 or EVE-NG suggestion based on chapter complexity
- Required device images and where to legally obtain them (Cisco needs a CCO account, etc.)
- IP addressing scheme
- Step-by-step config snippets

### Pentest

Use for:
- Web app testing, exploitation, reverse engineering
- CTF-style challenges

Lab guide should include:
- Target VM suggestion: HTB Academy, TryHackMe room, VulnHub box, or DVWA
  - Be specific: name a relevant box if one fits the chapter's topic
- Attacker box: Kali Linux, Parrot OS, or whatever the book recommends
- Network isolation reminder (host-only or NAT, never bridged to a real network when running noisy tools)
- Tool installation if not preinstalled
- A clear note: this lab is for authorised systems only

## Things to never do

- Never produce a lab that completes the primary learning task. If the chapter teaches the user to write a port scanner, the lab sets up the environment and gives them the structure to write their own scanner. It does not give them a finished scanner to run.
- Never include real credentials, real targets, or real customer data.
- Never invent VM specs or eval-centre URLs. If you don't know, link to the publisher of the OS and let the user navigate from there.
- Never recommend running pentesting tools against arbitrary internet hosts.
