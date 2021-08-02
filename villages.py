import math


class VillageIndex:

    def __init__(self):
        self.villages = set()

    def add_village(self, name: str, x: int, z: int) -> None:
        self.villages.add((name, x, z))

    def get_closest_village(self, x: int, z: int) -> str:
        # maps village names to the distance between the village and (x, z)
        village_dists: dict[str, int] = {}
        for village in self.villages:
            village_x, village_z = village[1:]
            village_dists[village[0]] = math.dist((village_x, village_z),
                                                  (x, z))
        result = min(village_dists.items(), key=lambda x: x[1])
        if result[1] > 1000:
            return "no registered villages within 1000 blocks"
        else:
            return result[0]


village_index = VillageIndex()
village_index.add_village("cuteville", 0, 0)
village_index.add_village("russel village", 750, 500)
village_index.add_village("vatican city", 2200, -1400)
village_index.add_village("acacia town", 1600, -1000)
