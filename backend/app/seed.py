"""Seeds the database with the 17 carriers from the LogiConnect prototype.

Run with:  python -m app.seed
"""

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal, init_models
from app.models import CarrierProfile

RAW_CARRIERS = [
    dict(name="Julien Moreau", type="individuel", city="Paris", vehicle="scooter",
         package_types=["documents", "petit_colis"], base_price=15, price_per_km=0.9,
         zones_served=["Paris", "Île-de-France", "Versailles", "Boulogne-Billancourt"],
         rating=4.8, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 1h", verified=True, completed_deliveries=540, years_active=3,
         bio="Coursier indépendant à Paris, spécialisé dans les livraisons express de documents et petits colis en scooter électrique."),

    dict(name="TransExpress Lyon", type="entreprise", city="Lyon", vehicle="camionnette",
         package_types=["petit_colis", "colis_volumineux", "fragile"], base_price=35, price_per_km=1.1,
         zones_served=["Lyon", "Villeurbanne", "Saint-Étienne", "Grenoble"],
         rating=4.6, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Matin", "Après-midi", "Soir"],
         response_time="< 2h", verified=True, completed_deliveries=1200, years_active=6,
         bio="Société de transport régional basée à Lyon. Flotte de camionnettes équipées pour les colis volumineux et fragiles."),

    dict(name="Amélie Petit — Coursière Pro", type="individuel", city="Bordeaux", vehicle="velo",
         package_types=["documents", "petit_colis"], base_price=10, price_per_km=0.7,
         zones_served=["Bordeaux", "Mérignac", "Pessac"],
         rating=4.9, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 30 min", verified=True, completed_deliveries=860, years_active=4,
         bio="Livraison à vélo cargo, écoresponsable, dans le centre de Bordeaux et ses environs immédiats."),

    dict(name="Nord Fret Express", type="entreprise", city="Lille", vehicle="camion",
         package_types=["palette", "colis_volumineux"], base_price=60, price_per_km=1.4,
         zones_served=["Lille", "Roubaix", "Tourcoing", "Dunkerque"],
         rating=4.4, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 4h", verified=True, completed_deliveries=410, years_active=9,
         bio="Spécialiste du transport de palettes et de marchandises volumineuses dans les Hauts-de-France."),

    dict(name="Sophie Lambert", type="individuel", city="Nantes", vehicle="voiture",
         package_types=["documents", "petit_colis", "fragile"], base_price=18, price_per_km=0.85,
         zones_served=["Nantes", "Saint-Nazaire", "Rezé"],
         rating=4.7, available_days=["Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Après-midi", "Soir"],
         response_time="< 1h30", verified=False, completed_deliveries=190, years_active=2,
         bio="Transport soigné de colis fragiles et documents importants en voiture. Disponible en soirée pour les envois de dernière minute."),

    dict(name="Rapid'Colis Marseille", type="entreprise", city="Marseille", vehicle="camionnette",
         package_types=["petit_colis", "colis_volumineux"], base_price=28, price_per_km=1.0,
         zones_served=["Marseille", "Aix-en-Provence", "Aubagne"],
         rating=4.3, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Matin", "Après-midi"],
         response_time="< 2h", verified=True, completed_deliveries=980, years_active=5,
         bio="Livraisons rapides sur toute l'agglomération marseillaise, du colis simple au volumineux."),

    dict(name="Karim Belkacem", type="individuel", city="Toulouse", vehicle="scooter",
         package_types=["documents", "petit_colis"], base_price=12, price_per_km=0.8,
         zones_served=["Toulouse", "Blagnac", "Colomiers"],
         rating=4.5, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi", "Soir"],
         response_time="< 1h", verified=True, completed_deliveries=320, years_active=2,
         bio="Coursier scooter réactif, spécialiste des livraisons urgentes dans l'agglomération toulousaine."),

    dict(name="Océane Fournier", type="individuel", city="Rennes", vehicle="voiture",
         package_types=["petit_colis", "fragile", "documents"], base_price=16, price_per_km=0.9,
         zones_served=["Rennes", "Saint-Malo", "Vitré"],
         rating=4.9, available_days=["Lun", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 1h", verified=True, completed_deliveries=410, years_active=3,
         bio="Livraison soignée et ponctuelle en Bretagne, expérience particulière avec les objets fragiles et précieux."),

    dict(name="Alpine Logistique", type="entreprise", city="Grenoble", vehicle="camion",
         package_types=["palette", "colis_volumineux", "fragile"], base_price=55, price_per_km=1.3,
         zones_served=["Grenoble", "Chambéry", "Annecy"],
         rating=4.2, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 3h", verified=True, completed_deliveries=275, years_active=7,
         bio="Transport de marchandises en zone alpine, y compris trajets en altitude et conditions hivernales."),

    dict(name="Camille Girard", type="individuel", city="Strasbourg", vehicle="velo",
         package_types=["documents", "petit_colis"], base_price=9, price_per_km=0.65,
         zones_served=["Strasbourg", "Schiltigheim", "Illkirch-Graffenstaden"],
         rating=4.8, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Matin", "Après-midi"],
         response_time="< 45 min", verified=True, completed_deliveries=702, years_active=4,
         bio="Coursière à vélo cargo, livraisons rapides et écologiques dans l'Eurométropole de Strasbourg."),

    dict(name="Sud Transport Express", type="entreprise", city="Montpellier", vehicle="camionnette",
         package_types=["petit_colis", "colis_volumineux", "palette"], base_price=32, price_per_km=1.05,
         zones_served=["Montpellier", "Nîmes", "Sète"],
         rating=4.5, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi", "Soir"],
         response_time="< 2h", verified=True, completed_deliveries=650, years_active=5,
         bio="Transporteur régional couvrant l'Hérault et le Gard, du colis unique aux tournées régulières."),

    dict(name="Thomas Bernard", type="individuel", city="Nice", vehicle="voiture",
         package_types=["documents", "petit_colis", "fragile"], base_price=20, price_per_km=0.95,
         zones_served=["Nice", "Cannes", "Antibes"],
         rating=4.6, available_days=["Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Après-midi", "Soir"],
         response_time="< 1h30", verified=False, completed_deliveries=230, years_active=2,
         bio="Livraisons sur la Côte d'Azur, spécialiste des trajets combinant clientèle touristique et professionnelle."),

    dict(name="France Colis National", type="entreprise", city="Paris", vehicle="camion",
         package_types=["petit_colis", "colis_volumineux", "palette", "fragile"], base_price=45, price_per_km=1.2,
         zones_served=["Paris", "Lyon", "Marseille", "Toulouse", "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille", "Rennes", "Grenoble", "Nice"],
         rating=4.4, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 3h", verified=True, completed_deliveries=2100, years_active=11,
         external_network="colissimo",
         bio="Réseau national de transport interurbain. Liaisons régulières entre les grandes métropoles françaises, tous types de colis."),

    dict(name="RoutePartner Colis", type="entreprise", city="Lyon", vehicle="camionnette",
         package_types=["documents", "petit_colis", "colis_volumineux"], base_price=38, price_per_km=1.0,
         zones_served=["Lyon", "Paris", "Marseille", "Toulouse", "Bordeaux", "Nantes", "Strasbourg", "Lille", "Montpellier"],
         rating=4.5, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Matin", "Après-midi", "Soir"],
         response_time="< 2h", verified=True, completed_deliveries=1450, years_active=8,
         external_network="chronopost",
         bio="Transporteur interurbain basé à Lyon, liaisons quotidiennes vers les principales villes de France."),

    dict(name="Téranga Air Cargo", type="entreprise", city="Dakar", vehicle="avion",
         package_types=["documents", "petit_colis", "colis_volumineux", "fragile"], base_price=35, price_per_km=0.02,
         zones_served=["Dakar", "Paris", "Marseille", "Lyon"],
         rating=4.6, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin", "Après-midi"],
         response_time="< 4h", verified=True, completed_deliveries=890, years_active=6,
         delivery_estimate="3 à 5 jours ouvrés", external_network="dhl",
         bio="Spécialiste du fret aérien entre Dakar et la France (Paris, Marseille, Lyon). Dédouanement inclus, livraison en 3 à 5 jours ouvrés."),

    dict(name="Sénégal Maritime Groupage", type="entreprise", city="Dakar", vehicle="bateau",
         package_types=["petit_colis", "colis_volumineux", "palette"], base_price=20, price_per_km=0.01,
         zones_served=["Dakar", "Paris", "Marseille"],
         rating=4.4, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven"], time_windows=["Matin"],
         response_time="< 6h", verified=True, completed_deliveries=540, years_active=9,
         delivery_estimate="3 à 5 semaines",
         bio="Transport maritime groupé (conteneur) entre le port de Dakar et les ports français. Solution économique pour colis volumineux et palettes, délai de 3 à 5 semaines."),

    dict(name="Moussa Diop", type="individuel", city="Dakar", vehicle="scooter",
         package_types=["documents", "petit_colis"], base_price=3, price_per_km=0.3,
         zones_served=["Dakar", "Pikine", "Guédiawaye", "Parcelles Assainies", "Rufisque"],
         rating=4.7, available_days=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"], time_windows=["Matin", "Après-midi", "Soir"],
         response_time="< 30 min", verified=True, completed_deliveries=610, years_active=4,
         bio="Coursier indépendant basé à Dakar, livraisons rapides en scooter dans l'agglomération dakaroise (Plateau, Pikine, Parcelles Assainies, Guédiawaye, Rufisque)."),
]


async def seed():
    await init_models()
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(CarrierProfile.id).limit(1))
        if existing.scalar_one_or_none():
            print("Carriers already seeded — skipping. Delete rows manually to reseed.")
            return

        for raw in RAW_CARRIERS:
            data = dict(raw)
            data["external_network"] = data.get("external_network", "none")
            data["review_count"] = round(40 + data["completed_deliveries"] / 6)
            db.add(CarrierProfile(**data))

        await db.commit()
        print(f"Seeded {len(RAW_CARRIERS)} carriers.")


if __name__ == "__main__":
    asyncio.run(seed())
