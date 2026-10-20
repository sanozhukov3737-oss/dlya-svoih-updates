package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import ru.dlyasvoih.app.R

private data class MenuIconSpec(val drawable: Int = 0, val photo: Int = 0)

// Menu photos are application resources, independent of catalog pack replacement.
// These are unchanged copies of the previously reviewed representative thumbnails.
private val menuIconSpecs = mapOf(
    "AMMUNITION" to MenuIconSpec(drawable = R.drawable.icon_catalog_ammunition),
    "ATGM" to MenuIconSpec(drawable = R.drawable.icon_catalog_atgm),
    "atgm-reference" to MenuIconSpec(drawable = R.drawable.icon_catalog_atgm),
    "SVO" to MenuIconSpec(drawable = R.drawable.icon_catalog_drone),
    "sources" to MenuIconSpec(drawable = R.drawable.icon_catalog_drone),
    "@uav" to MenuIconSpec(drawable = R.drawable.icon_catalog_drone),
    "uav-drop-munitions" to MenuIconSpec(drawable = R.drawable.icon_catalog_air_munition),
    "uav-warheads" to MenuIconSpec(drawable = R.drawable.icon_catalog_charges),
    "uav-release-systems" to MenuIconSpec(drawable = R.drawable.icon_catalog_drone),
    "munition-components" to MenuIconSpec(drawable = R.drawable.icon_catalog_charges),
    "rocket-motors" to MenuIconSpec(drawable = R.drawable.icon_catalog_rocket),
    "weapon-components" to MenuIconSpec(drawable = R.drawable.icon_catalog_artillery),
    "vehicle-components" to MenuIconSpec(drawable = R.drawable.icon_catalog_catalog),
    "MEDICINE" to MenuIconSpec(drawable = R.drawable.icon_catalog_first_aid),
    "first-aid" to MenuIconSpec(drawable = R.drawable.icon_catalog_first_aid),
    "@engineering" to MenuIconSpec(photo = R.drawable.menu_photo_antitank),
    "@initiation" to MenuIconSpec(drawable = R.drawable.icon_catalog_fuzes),
    "fuzes" to MenuIconSpec(drawable = R.drawable.icon_catalog_fuzes),
    "@all" to MenuIconSpec(drawable = R.drawable.icon_catalog_catalog),
    "engineering" to MenuIconSpec(drawable = R.drawable.icon_catalog_book),
    "reference" to MenuIconSpec(drawable = R.drawable.icon_catalog_book),
    "grenades" to MenuIconSpec(drawable = R.drawable.icon_catalog_grenade),
    "mortars" to MenuIconSpec(drawable = R.drawable.icon_catalog_mortar),
    "artillery" to MenuIconSpec(drawable = R.drawable.icon_catalog_artillery),
    "cannon-ammunition" to MenuIconSpec(drawable = R.drawable.icon_catalog_cannon_ammunition),
    "rockets-recoilless" to MenuIconSpec(drawable = R.drawable.icon_catalog_rocket),
    "air-munitions" to MenuIconSpec(drawable = R.drawable.icon_catalog_air_munition),
    "submunitions" to MenuIconSpec(photo = R.drawable.menu_photo_submunitions),
    "audit-candidates" to MenuIconSpec(drawable = R.drawable.icon_catalog_audit),
    "charges" to MenuIconSpec(drawable = R.drawable.icon_catalog_charges),
    "mines-antipersonnel" to MenuIconSpec(photo = R.drawable.menu_photo_antipersonnel),
    "mines-antitank" to MenuIconSpec(photo = R.drawable.menu_photo_antitank),
    "mines-antibottom" to MenuIconSpec(drawable = R.drawable.icon_catalog_mines_antibottom),
    "mines-antivehicle" to MenuIconSpec(photo = R.drawable.menu_photo_antivehicle),
    "mines-naval" to MenuIconSpec(photo = R.drawable.menu_photo_naval),
    "mines-anchored" to MenuIconSpec(drawable = R.drawable.icon_catalog_mines_anchored),
    "mines-antiland" to MenuIconSpec(photo = R.drawable.menu_photo_antiland),
    "mines-special" to MenuIconSpec(photo = R.drawable.menu_photo_special),
    "ied" to MenuIconSpec(drawable = R.drawable.icon_catalog_ied),
    "ignition-electric" to MenuIconSpec(drawable = R.drawable.icon_catalog_ignition_electric),
    "detonators-caps" to MenuIconSpec(drawable = R.drawable.icon_catalog_detonators_caps),
    "primers" to MenuIconSpec(drawable = R.drawable.icon_catalog_primers),
    "detonators-electric" to MenuIconSpec(drawable = R.drawable.icon_catalog_detonators_electric),
    "fuse-cord" to MenuIconSpec(drawable = R.drawable.icon_catalog_fuse_cord),
    "detonating-cord" to MenuIconSpec(drawable = R.drawable.icon_catalog_detonating_cord),
    "sapper-wires" to MenuIconSpec(drawable = R.drawable.icon_catalog_sapper_wires),
    "blasting-machines" to MenuIconSpec(drawable = R.drawable.icon_catalog_blasting_machines),
    "measuring-instruments" to MenuIconSpec(drawable = R.drawable.icon_catalog_measuring_instruments),
    "ignition-tubes" to MenuIconSpec(drawable = R.drawable.icon_catalog_ignition_tubes),
    "mine-fuzes" to MenuIconSpec(drawable = R.drawable.icon_catalog_mine_fuzes),
    "grenade-fuzes" to MenuIconSpec(drawable = R.drawable.icon_catalog_grenade_fuzes),
    "artillery-fuzes" to MenuIconSpec(drawable = R.drawable.icon_catalog_artillery_fuzes),
    "detonators-nonelectric" to MenuIconSpec(drawable = R.drawable.icon_catalog_detonators_nonelectric),
    "detonators-electronic" to MenuIconSpec(drawable = R.drawable.icon_catalog_detonators_electronic),
 )

internal fun catalogMenuIconResource(key: String, useRepresentativePhoto: Boolean = true): Int {
    val spec = menuIconSpecs[key] ?: MenuIconSpec(drawable = R.drawable.icon_catalog_catalog)
    return if (useRepresentativePhoto && spec.photo != 0) spec.photo
        else if (spec.drawable != 0) spec.drawable else R.drawable.icon_catalog_ammunition
}

/** Offline decorative menu icon. The containing row supplies its accessible label. */
@Composable
fun CatalogMenuIcon(key: String, modifier: Modifier = Modifier, useRepresentativePhoto: Boolean = true) {
    val shape = RoundedCornerShape(14.dp)
    Box(
        modifier = modifier
            .size(64.dp)
            .clip(shape)
            .background(Color.White)
            .border(1.dp, Color(0xFFE1E4D9), shape)
            .padding(6.dp)
            .clearAndSetSemantics { },
        contentAlignment = Alignment.Center
    ) {
        Image(
            painter = painterResource(catalogMenuIconResource(key, useRepresentativePhoto)),
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxSize()
        )
    }
}
