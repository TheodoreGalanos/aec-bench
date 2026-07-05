# ABOUTME: Source-bounded notes for the SSC-13 road visual operations synthetic source pack.
# ABOUTME: Captures current external workflow facts used to shape the task-owned fixture.

# Scraped Notes

These notes are source routes for workflow shape only. The baseline source pack is task-owned and synthetic.

## Lighting Calculation Workflow

- AGi32 presents itself as photometric calculation software for lighting design and analysis, including indoor and outdoor applications, point-by-point illuminance, luminance, glare/daylight metrics, CAD import, photometric data, renderings, maps, roadway analyses, and reports.
- DIALux road lighting starts from a planning basis, selected standard, road profile, lighting class, luminaire arrangement, optimization, evaluation fields, isolux charts, value charts, and grid-point photometric tables.

## Traffic-Control And Message-Policy Workflow

- FHWA states that the 11th Edition of the MUTCD with Revision 1, dated December 2025, is the current official FHWA publication, available as the official PDF.
- The synthetic pack uses a task-owned VMS message policy rather than reproducing standard text. A future source-pack hardening pass should bind any extracted traffic-control rule to the current official MUTCD PDF and owner message library.

## CCTV Coverage Workflow

- AXIS Site Designer supports adding floorplans or maps, placing cameras and devices, viewing coverage, estimating bandwidth and storage, estimating power consumption, generating bills of materials, and sharing site notes with installers.
- JVSG-style CCTV design tooling is a route for camera placement, pixel density, bandwidth, storage, and field-of-view reasoning; the synthetic pack captures the simple PPM/storage subset.

## ITS Communications Workflow

- ARC-IT is the source route for ITS architecture and communications views.
- The NTCIP document list exposes current routes for dynamic message signs, CCTV camera control, electrical and lighting management systems, Ethernet profiles, and TCP/IP/UDP transport profiles.

## Fixture Implication

The first runnable synthetic fixture should not try to model full lighting physics or full MUTCD compliance. It should verify a closed source pack: object IDs, source status, lighting summary, CCTV PPM/storage, network bandwidth, PoE load, fibre margin, UPS demand, and memo traceability.
