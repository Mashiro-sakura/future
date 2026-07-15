from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdminUser, Product
from app.security import hash_password


DEFAULT_PRODUCTS = [
    {
        "code": "PTA",
        "name": "PTA",
        "futures_symbol": "TA0",
        "spot_symbol": "PTA",
        "exchange": "CZCE",
        "display_order": 1,
    },
    {
        "code": "PVC",
        "name": "PVC",
        "futures_symbol": "V0",
        "spot_symbol": "PVC",
        "exchange": "DCE",
        "display_order": 2,
    },
    {
        "code": "LLDPE",
        "name": "线型低密度聚乙烯",
        "futures_symbol": "L0",
        "spot_symbol": "LLDPE",
        "exchange": "DCE",
        "display_order": 3,
    },
    {
        "code": "PP",
        "name": "聚丙烯",
        "futures_symbol": "PP0",
        "spot_symbol": "PP",
        "exchange": "DCE",
        "display_order": 4,
    },
    {
        "code": "PB",
        "name": "沪铅",
        "futures_symbol": "PB0",
        "spot_symbol": "沪铅",
        "exchange": "SHFE",
        "display_order": 5,
    },
    {
        "code": "P",
        "name": "棕榈油",
        "futures_symbol": "P0",
        "spot_symbol": "棕榈油",
        "exchange": "DCE",
        "display_order": 6,
    },
    {
        "code": "PL",
        "name": "丙烯",
        "futures_symbol": "PL0",
        "spot_symbol": "丙烯",
        "exchange": "CZCE",
        "display_order": 7,
    },
    {
        "code": "PX",
        "name": "PX",
        "futures_symbol": "PX0",
        "spot_symbol": "PX",
        "exchange": "CZCE",
        "display_order": 8,
    },
    {
        "code": "CU",
        "name": "沪铜",
        "futures_symbol": "CU0",
        "spot_symbol": "沪铜",
        "exchange": "SHFE",
        "display_order": 9,
    },
    {
        "code": "OCT",
        "name": "辛醇",
        "futures_symbol": "",
        "spot_symbol": "辛醇",
        "exchange": "SPOT",
        "display_order": 10,
    },
]


def seed_database(db: Session) -> None:
    for product_data in DEFAULT_PRODUCTS:
        exists = db.query(Product).filter(Product.code == product_data["code"]).first()
        if exists:
            for key, value in product_data.items():
                setattr(exists, key, value)
            exists.is_active = True
        else:
            db.add(Product(**product_data))

    settings = get_settings()
    admin = db.query(AdminUser).filter(AdminUser.username == settings.admin_username).first()
    if not admin:
        db.add(
            AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="admin",
                is_active=True,
            )
        )
    db.commit()
