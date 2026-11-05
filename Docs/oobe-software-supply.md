# OOBE software supply and provenance

Research and engineering policy, checked November 5, 2026. The two incoming factory/OOBE robots have not been inventoried. A failed first boot does not yet establish which software is absent: configuration, provisioning, installation state or unavailable services may also prevent startup. This guide records the investigation and release design; it is not legal clearance for a firmware image or converter.

## Delivery design

We do not have an established permission to mirror Jibo's proprietary update images. Jibo having distributed an update does not itself authorize another distributor to copy it. Hardware ownership and resale also do not automatically convey software reproduction or distribution rights. The U.S. starting points are [17 USC 106, 109 and 117](https://www.copyright.gov/title17/92chap1.html).

A complete OS replacement is not established as necessary. Determine the actual missing components first, then use the smallest supportable path:

| Component route | Evidence required before use in a public deliverable |
| --- | --- |
| Independently authored OpenJibo code | Origin, declared license and dependencies recorded |
| Licensed third-party component | Applicable license and exact version, permission for the intended distribution/use, notices and source/build obligations fulfilled |
| Existing vendor component retained on the owner's own robot | Lawful source and applicable terms identified; modification, commercial use and circumvention aspects reviewed; files remain local |
| Authorized owner download | Actual supplier authority and terms permit this owner's installation; a working historical URL alone is insufficient |
| Missing proprietary component | Permission from the appropriate rightsholder/licensor, or an independently developed replacement |
| Unknown origin or rights | Keep outside release payloads until the evidence is resolved |

Owner-local processing, a binary delta, a rebuilt image or a user-supplied file is not automatic legal clearance. A Linux-based image can contain separately licensed drivers, runtime binaries, voice models, animations and other content. [GPLv2](https://raw.githubusercontent.com/torvalds/linux/master/LICENSES/preferred/GPL-2.0) provides redistribution permissions for covered code under its conditions, including applicable corresponding-source obligations; it does not license every bundled component.

The [historical October 19, 2017 Jibo EULA](https://jibo.media.mit.edu/wp-content/uploads/2018/03/EULA_WARRANTY_OCT20-PDF.pdf) covers updates, restricts transfer/commercial use and recognizes separate third-party/open-source terms. Identify the terms applicable to each actual release and robot. That document neither establishes the current rightsholder nor decides the enforceability of a particular restriction. Review commercial hosted-service use of retained components as well as firmware redistribution.

## Intake when the units arrive

1. Retain a separate read-only backup and acquisition record for each robot. Preserve its identity, keys, calibration and recovery data privately. Do not clone the working robot's identity or calibration into an incoming robot.
2. Identify factory release/build identifiers, boot/install state, update manifests and bundled license/notice files from the retained evidence. Record actual paths and byte hashes; unknown values stay unknown.
3. Use the [pre-provisioning storage intake](oobe-storage-intake.md) for its narrow credential observations and the [recovery-table audit](gpt-recovery-audit.md) for its table checks. Neither tool inventories all installed software, proves a factory release, supplies credentials, establishes software rights or approves a write.
4. Compare the required capabilities with the working robot. Distinguish an absent executable or model from a file already present but blocked by configuration or service dependency. Do not infer a missing OS from an OOBE screen alone.
5. Inventory each required component and select a documented delivery route. Missing proprietary files remain a supply gap until an authorized source, license or replacement is established.
6. Produce a per-unit upgrade/recovery plan with exact inputs, compatibility evidence, complete change preview and rollback/readback acceptance. Existing conversion reviews remain previews; this document adds no physical apply capability.

## Component record

Keep the evidence privately alongside each retained backup, using a local alias rather than publishing a robot's serial, credentials or backup. A record should include:

| Field | Meaning |
| --- | --- |
| Component and role | Actual file/package/model/content and capability it supplies |
| Observation | Present, absent within a defined inspected scope, or unobserved; include scope and parser limits |
| Version, location and SHA-256 | Measured facts, with links to the retained private evidence |
| Origin and supplier | Where the exact bytes came from; authority of any download/distributor |
| License and notices | Exact applicable text/version and evidence; include separate third-party terms |
| Proposed route and audience | Owner-local retention, authorized download, licensed redistribution, independent replacement or unresolved; personal and commercial uses distinguished |
| Obligations and fulfillment | Notices, corresponding source, build materials and other applicable conditions, with retained fulfillment evidence |
| Review and gaps | Reviewer, date, specific basis and unresolved questions; no default approval for an empty record |

Keep observation separate from legal conclusions. Matching bytes show consistency with the compared file, not a distribution right. No component inventory or rights clearance has yet been completed for the incoming robots.

## Repair and interoperability questions

The [2024 final exemption rule](https://www.govinfo.gov/content/pkg/FR-2024-10-28/pdf/2024-24563.pdf), 37 CFR 201.40(b)(11) and (15), includes potentially relevant voice-assistant interoperability and consumer-device repair classes. Qualification of Jibo and the actual conversion process requires review. These exemptions and the qualified interoperability provisions in [17 USC 1201](https://www.copyright.gov/title17/92chap12.html) do not provide blanket firmware redistribution permission; copying, contract and tool-distribution questions are separate.

Before publishing a package containing proprietary firmware or shipping a commercial conversion path, give qualified software/IP counsel the exact proposed artifacts, applicable licenses, acquisition facts, intended personal/commercial uses and conversion steps. Resolve both the supply of missing components and any circumvention/tool-distribution issues for the intended jurisdictions. Do not infer present rightsholder identity from an old acquisition announcement or community mirror.

Independently authored platform work and releases can continue under their applicable licenses. This investigation has supplied no proprietary update image and has not modified an incoming robot.
