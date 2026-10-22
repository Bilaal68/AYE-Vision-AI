"""Seed demo cameras, zones, rules, alerts, registered persons (faces), and registered vehicles."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.organization import Organization
from app.models.camera import Camera, StreamProtocol, RecordingMode
from app.models.zone import Zone, ZoneType
from app.models.rule import Rule, RuleType, RuleSeverity
from app.models.alert import Alert, AlertStatus
from app.models.person import Person, PersonType
from app.models.vehicle import Vehicle, VehicleCategory

async def seed_data():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            # Get default organization
            org_res = await session.execute(select(Organization).limit(1))
            org = org_res.scalar_one_or_none()
            if not org:
                print("No organization found. Please run scripts/seed_data.py first.")
                return

            print(f"Using Organization: {org.name} ({org.id})")

            # 1. Seed Sample Cameras
            cameras_def = [
                {
                    "name": "Main Entrance (Simulated Feed)",
                    "stream_url": "rtsp://mediamtx:8554/cam1",
                    "protocol": StreamProtocol.RTSP,
                    "location_description": "Main Gate - Gate 1",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "is_active": True,
                    "is_online": True,
                    "recording_mode": RecordingMode.CONTINUOUS,
                },
                {
                    "name": "Office Lobby (Simulated Feed)",
                    "stream_url": "rtsp://mediamtx:8554/cam2",
                    "protocol": StreamProtocol.RTSP,
                    "location_description": "Reception & Waiting Area",
                    "resolution": "1920x1080",
                    "fps": 25,
                    "is_active": True,
                    "is_online": True,
                    "recording_mode": RecordingMode.EVENT,
                },
                {
                    "name": "Parking Area North",
                    "stream_url": "rtsp://mediamtx:8554/cam3",
                    "protocol": StreamProtocol.RTSP,
                    "location_description": "North Parking Lot - Section B",
                    "resolution": "1280x720",
                    "fps": 20,
                    "is_active": True,
                    "is_online": True,
                    "recording_mode": RecordingMode.EVENT,
                }
            ]

            saved_cameras = {}
            for cam_data in cameras_def:
                existing = await session.execute(
                    select(Camera).where(Camera.name == cam_data["name"], Camera.org_id == org.id)
                )
                cam = existing.scalar_one_or_none()
                if not cam:
                    cam = Camera(
                        id=uuid.uuid4(),
                        org_id=org.id,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        **cam_data
                    )
                    session.add(cam)
                    await session.flush()
                    print(f"Added camera: {cam.name}")
                else:
                    print(f"Camera exists: {cam_data['name']}")
                saved_cameras[cam.name] = cam

            # 2. Seed Zones for each camera
            cam_main = saved_cameras.get("Main Entrance (Simulated Feed)")
            cam_lobby = saved_cameras.get("Office Lobby (Simulated Feed)")
            cam_park = saved_cameras.get("Parking Area North")

            zones_def = []
            if cam_main:
                zones_def.append({
                    "camera_id": cam_main.id,
                    "name": "Main Gate Perimeter",
                    "zone_type": ZoneType.RESTRICTED,
                    "polygon_points": [[0.1, 0.4], [0.9, 0.4], [0.9, 0.85], [0.1, 0.85]],
                    "color_hex": "#ef4444",
                })
            if cam_lobby:
                zones_def.append({
                    "camera_id": cam_lobby.id,
                    "name": "Reception Waiting Area",
                    "zone_type": ZoneType.MONITORING,
                    "polygon_points": [[0.15, 0.3], [0.85, 0.3], [0.85, 0.75], [0.15, 0.75]],
                    "color_hex": "#3b82f6",
                })
            if cam_park:
                zones_def.append({
                    "camera_id": cam_park.id,
                    "name": "Loading Bay Restricted",
                    "zone_type": ZoneType.RESTRICTED,
                    "polygon_points": [[0.2, 0.25], [0.8, 0.25], [0.8, 0.8], [0.2, 0.8]],
                    "color_hex": "#f59e0b",
                })

            saved_zones = {}
            for z_data in zones_def:
                existing_z = await session.execute(
                    select(Zone).where(Zone.name == z_data["name"], Zone.camera_id == z_data["camera_id"])
                )
                z = existing_z.scalar_one_or_none()
                if not z:
                    z = Zone(
                        id=uuid.uuid4(),
                        is_active=True,
                        **z_data
                    )
                    session.add(z)
                    await session.flush()
                    print(f"Added zone: {z.name}")
                saved_zones[z.name] = z

            # 3. Seed Rules for each camera
            rules_def = []
            if cam_main:
                rules_def.extend([
                    {
                        "camera_id": cam_main.id,
                        "rule_type": RuleType.INTRUSION_DETECTION,
                        "severity": RuleSeverity.CRITICAL,
                        "parameters": {"confidence_threshold": 0.85, "min_duration_seconds": 2},
                    },
                    {
                        "camera_id": cam_main.id,
                        "rule_type": RuleType.CROWD_FORMATION,
                        "severity": RuleSeverity.HIGH,
                        "parameters": {"max_people": 5, "duration_seconds": 10},
                    },
                    {
                        "camera_id": cam_main.id,
                        "rule_type": RuleType.PPE_VIOLATION,
                        "severity": RuleSeverity.MEDIUM,
                        "parameters": {"required_ppe": ["helmet", "vest"]},
                    },
                ])
            if cam_lobby:
                rules_def.extend([
                    {
                        "camera_id": cam_lobby.id,
                        "rule_type": RuleType.FACE_BLACKLISTED,
                        "severity": RuleSeverity.CRITICAL,
                        "parameters": {"min_confidence": 0.85},
                    },
                    {
                        "camera_id": cam_lobby.id,
                        "rule_type": RuleType.LOITERING,
                        "severity": RuleSeverity.MEDIUM,
                        "parameters": {"duration_seconds": 120},
                    },
                ])
            if cam_park:
                rules_def.extend([
                    {
                        "camera_id": cam_park.id,
                        "rule_type": RuleType.ANPR_BLACKLISTED,
                        "severity": RuleSeverity.CRITICAL,
                        "parameters": {"alert_on_match": True},
                    },
                    {
                        "camera_id": cam_park.id,
                        "rule_type": RuleType.ILLEGAL_PARKING,
                        "severity": RuleSeverity.HIGH,
                        "parameters": {"max_park_minutes": 15},
                    },
                ])

            saved_rules = {}
            for r_data in rules_def:
                existing_r = await session.execute(
                    select(Rule).where(
                        Rule.camera_id == r_data["camera_id"],
                        Rule.rule_type == r_data["rule_type"],
                        Rule.org_id == org.id,
                    )
                )
                r = existing_r.scalar_one_or_none()
                if not r:
                    r = Rule(
                        id=uuid.uuid4(),
                        org_id=org.id,
                        is_active=True,
                        cooldown_seconds=300,
                        **r_data
                    )
                    session.add(r)
                    await session.flush()
                    print(f"Added rule: {r.rule_type.value} on camera {r.camera_id}")
                saved_rules[(r.camera_id, r.rule_type)] = r

            # 4. Seed Realistic Alerts
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            alerts_def = []

            if cam_main:
                r_intrusion = saved_rules.get((cam_main.id, RuleType.INTRUSION_DETECTION))
                r_crowd = saved_rules.get((cam_main.id, RuleType.CROWD_FORMATION))
                r_ppe = saved_rules.get((cam_main.id, RuleType.PPE_VIOLATION))

                if r_intrusion:
                    alerts_def.append({
                        "camera_id": cam_main.id,
                        "rule_id": r_intrusion.id,
                        "alert_type": RuleType.INTRUSION_DETECTION,
                        "severity": RuleSeverity.CRITICAL,
                        "title": "Unauthorized Perimeter Intrusion",
                        "description": "Subject detected climbing boundary fence in restricted perimeter.",
                        "status": AlertStatus.NEW,
                        "created_at": now - timedelta(minutes=12),
                        "metadata_json": {"confidence": 0.96, "target": "Person", "zone": "Main Gate Perimeter"},
                    })
                    alerts_def.append({
                        "camera_id": cam_main.id,
                        "rule_id": r_intrusion.id,
                        "alert_type": RuleType.INTRUSION_DETECTION,
                        "severity": RuleSeverity.CRITICAL,
                        "title": "Gate 1 Sensor Line Crossed",
                        "description": "Motion detected in restricted access corridor after lockup.",
                        "status": AlertStatus.RESOLVED,
                        "created_at": now - timedelta(hours=14),
                        "metadata_json": {"confidence": 0.91, "target": "Person"},
                    })
                if r_crowd:
                    alerts_def.append({
                        "camera_id": cam_main.id,
                        "rule_id": r_crowd.id,
                        "alert_type": RuleType.CROWD_FORMATION,
                        "severity": RuleSeverity.HIGH,
                        "title": "Crowd Density Threshold Exceeded",
                        "description": "Rapid gathering of 8 persons detected at Gate 1 entryway.",
                        "status": AlertStatus.NEW,
                        "created_at": now - timedelta(hours=1, minutes=20),
                        "metadata_json": {"crowd_count": 8, "threshold": 5},
                    })
                if r_ppe:
                    alerts_def.append({
                        "camera_id": cam_main.id,
                        "rule_id": r_ppe.id,
                        "alert_type": RuleType.PPE_VIOLATION,
                        "severity": RuleSeverity.MEDIUM,
                        "title": "Safety Gear Violation: No Helmet",
                        "description": "Individual entered hazardous area without certified safety helmet.",
                        "status": AlertStatus.ACKNOWLEDGED,
                        "created_at": now - timedelta(hours=3, minutes=10),
                        "metadata_json": {"missing": ["helmet"], "confidence": 0.89},
                    })

            if cam_lobby:
                r_face = saved_rules.get((cam_lobby.id, RuleType.FACE_BLACKLISTED))
                r_loit = saved_rules.get((cam_lobby.id, RuleType.LOITERING))

                if r_face:
                    alerts_def.append({
                        "camera_id": cam_lobby.id,
                        "rule_id": r_face.id,
                        "alert_type": RuleType.FACE_BLACKLISTED,
                        "severity": RuleSeverity.CRITICAL,
                        "title": "Security Watchlist Subject Identified",
                        "description": "Facial match (94% confidence) against blacklisted person record.",
                        "status": AlertStatus.NEW,
                        "created_at": now - timedelta(minutes=35),
                        "metadata_json": {"person_name": "Blocked Person", "confidence": 0.94},
                    })
                if r_loit:
                    alerts_def.append({
                        "camera_id": cam_lobby.id,
                        "rule_id": r_loit.id,
                        "alert_type": RuleType.LOITERING,
                        "severity": RuleSeverity.MEDIUM,
                        "title": "Extended Loitering in Reception",
                        "description": "Individual stationary for over 180 seconds in waiting lounge.",
                        "status": AlertStatus.ACKNOWLEDGED,
                        "created_at": now - timedelta(hours=4, minutes=45),
                        "metadata_json": {"duration_seconds": 210},
                    })

            if cam_park:
                r_anpr = saved_rules.get((cam_park.id, RuleType.ANPR_BLACKLISTED))
                r_park = saved_rules.get((cam_park.id, RuleType.ILLEGAL_PARKING))

                if r_anpr:
                    alerts_def.append({
                        "camera_id": cam_park.id,
                        "rule_id": r_anpr.id,
                        "alert_type": RuleType.ANPR_BLACKLISTED,
                        "severity": RuleSeverity.CRITICAL,
                        "title": "Blacklisted Vehicle Detected: SUS-9999",
                        "description": "Suspicious Ford Explorer with plate SUS-9999 observed in Section B.",
                        "status": AlertStatus.NEW,
                        "created_at": now - timedelta(minutes=50),
                        "metadata_json": {"plate": "SUS-9999", "vehicle": "Ford Explorer", "color": "Black"},
                    })
                if r_park:
                    alerts_def.append({
                        "camera_id": cam_park.id,
                        "rule_id": r_park.id,
                        "alert_type": RuleType.ILLEGAL_PARKING,
                        "severity": RuleSeverity.HIGH,
                        "title": "Unauthorized Parking in Loading Bay",
                        "description": "Vehicle obstructed emergency freight passage for over 20 minutes.",
                        "status": AlertStatus.RESOLVED,
                        "created_at": now - timedelta(hours=8),
                        "metadata_json": {"duration_minutes": 22},
                    })

            for a_data in alerts_def:
                existing_a = await session.execute(
                    select(Alert).where(
                        Alert.title == a_data["title"],
                        Alert.camera_id == a_data["camera_id"],
                        Alert.org_id == org.id,
                    )
                )
                if not existing_a.scalar_one_or_none():
                    alert_obj = Alert(
                        id=uuid.uuid4(),
                        org_id=org.id,
                        snapshot_path=f"/api/v1/cameras/{a_data['camera_id']}/snapshot",
                        updated_at=a_data["created_at"],
                        **a_data
                    )
                    session.add(alert_obj)
                    print(f"Added alert: {alert_obj.title} ({alert_obj.severity.value})")

            # 5. Seed Sample Vehicles
            vehicles = [
                {
                    "plate_number": "AA-3-A1234",
                    "make": "Toyota",
                    "model_name": "Hilux",
                    "color": "White",
                    "category": VehicleCategory.WHITELIST,
                    "owner_name": "Zero Trace Admin",
                    "notes": "Company security pickup truck",
                },
                {
                    "plate_number": "ET-2-B5678",
                    "make": "Hyundai",
                    "model_name": "Tucson",
                    "color": "Silver",
                    "category": VehicleCategory.EMPLOYEE,
                    "owner_name": "Staff Member",
                    "notes": "Daily commuter",
                },
                {
                    "plate_number": "SUS-9999",
                    "make": "Ford",
                    "model_name": "Explorer",
                    "color": "Black",
                    "category": VehicleCategory.BLACKLIST,
                    "owner_name": "Unknown Suspect",
                    "notes": "Alert security immediately upon entry",
                }
            ]

            for veh_data in vehicles:
                existing = await session.execute(
                    select(Vehicle).where(Vehicle.plate_number == veh_data["plate_number"], Vehicle.org_id == org.id)
                )
                if not existing.scalar_one_or_none():
                    veh = Vehicle(
                        id=uuid.uuid4(),
                        org_id=org.id,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        **veh_data
                    )
                    session.add(veh)
                    print(f"Added vehicle: {veh.plate_number}")
                else:
                    print(f"Vehicle exists: {veh_data['plate_number']}")

            # 6. Seed Sample Persons
            persons = [
                {
                    "full_name": "John Doe",
                    "person_type": PersonType.EMPLOYEE,
                    "department": "Security Intelligence",
                    "employee_id": "ZT-001",
                    "notes": "Lead Engineer - Zero Trace INSA 5th Btch",
                },
                {
                    "full_name": "Jane Smith",
                    "person_type": PersonType.VIP,
                    "department": "Operations",
                    "employee_id": "ZT-002",
                    "notes": "Authorized for High Security Areas",
                },
                {
                    "full_name": "Blocked Person",
                    "person_type": PersonType.BLACKLISTED,
                    "department": "External",
                    "employee_id": "UNK-999",
                    "notes": "Access restricted across all gates",
                }
            ]

            for per_data in persons:
                existing = await session.execute(
                    select(Person).where(Person.full_name == per_data["full_name"], Person.org_id == org.id)
                )
                if not existing.scalar_one_or_none():
                    per = Person(
                        id=uuid.uuid4(),
                        org_id=org.id,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        **per_data
                    )
                    session.add(per)
                    print(f"Added person: {per.full_name}")
                else:
                    print(f"Person exists: {per_data['full_name']}")

    await engine.dispose()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
