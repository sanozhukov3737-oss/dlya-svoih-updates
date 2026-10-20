package ru.dlyasvoih.app.ui;

import java.util.Arrays;
import java.util.List;

/** Exercise real menu grouping and routes without Android dependencies. */
public final class HostUavHierarchyChecks {
    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        List<String> available = Arrays.asList("mines-antitank", "grenades", "fuzes",
                "uav-drop-munitions", "uav-warheads", "uav-release-systems", "future-category", "reference");
        List<String> root = CatalogHierarchy.rootIds(available);
        require(root.contains(CatalogHierarchy.UAV_GROUP), "UAV group missing");
        require(CatalogHierarchy.uavIds(available).equals(Arrays.asList(
                "uav-drop-munitions", "uav-warheads", "uav-release-systems")), "Wrong UAV children");
        for (String child : CatalogHierarchy.uavIds(available))
            require(!root.contains(child), "Duplicate category at root: " + child);
        require(root.contains("future-category"), "Future categories became unreachable");
        require(!root.contains("reference"), "Hidden category exposed");
        require(CatalogHierarchy.uavIds(Arrays.asList("uav-warheads")).equals(Arrays.asList("uav-warheads")),
                "Partial content update cannot open its available child");
        require(!CatalogHierarchy.rootIds(Arrays.asList("grenades")).contains(CatalogHierarchy.UAV_GROUP),
                "Empty group shown before content arrives");
        require("catalog/uav".equals(CatalogHierarchy.groupRoute(CatalogHierarchy.UAV_GROUP)), "Wrong UAV route");
        require("catalog/engineering".equals(CatalogHierarchy.groupRoute(CatalogHierarchy.ENGINEERING_GROUP)),
                "Engineering route changed");
        require("catalog/initiation".equals(CatalogHierarchy.groupRoute(CatalogHierarchy.INITIATION_GROUP)),
                "Initiation route changed");
        try {
            CatalogHierarchy.groupRoute("@unknown");
            throw new AssertionError("Unknown group silently misrouted");
        } catch (IllegalArgumentException expected) { }
        System.out.println("UAV hierarchy checks passed");
    }
}
