package ru.dlyasvoih.app

import android.net.Uri
import android.content.pm.ApplicationInfo
import android.os.SystemClock
import androidx.compose.animation.Crossfade
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.data.CatalogFilter
import ru.dlyasvoih.app.data.MainSection
import ru.dlyasvoih.app.ui.*
import ru.dlyasvoih.app.ui.screens.*
import kotlinx.coroutines.delay

private enum class Tab(val route: String, val label: String, val icon: Int) {
    CATALOG("catalog", "Каталог", R.drawable.icon_ui_catalog),
    SEARCH("search_tab", "Поиск", R.drawable.icon_ui_search),
    FAVORITES("favorites_tab", "Избранное", R.drawable.icon_ui_star),
    HISTORY("history_tab", "Недавние", R.drawable.icon_ui_history)
}

@Composable
fun DlyaSvoihApp(shortcutRequest: State<ShortcutRequest?> = remember { mutableStateOf(null) }) {
    val context = LocalContext.current
    val repo = (context.applicationContext as GuideApplication).repository
    val boot: BootstrapViewModel = viewModel(factory = remember(repo) {
        viewModelFactory { initializer { BootstrapViewModel(repo) } }
    })
    val state by boot.state.collectAsStateWithLifecycle()
    // Database initialization already runs in the ViewModel. The short intro shares
    // that time, survives rotation, and does not run again when resuming this Activity.
    val introDeadline = rememberSaveable { SystemClock.elapsedRealtime() + 900L }
    var introDone by remember { mutableStateOf(SystemClock.elapsedRealtime() >= introDeadline) }
    LaunchedEffect(introDeadline) {
        delay((introDeadline - SystemClock.elapsedRealtime()).coerceIn(0L, 900L))
        introDone = true
    }
    val displayedState = if (state == BootState.Ready && !introDone) BootState.Loading else state
    Surface(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
        Crossfade(targetState = displayedState, animationSpec = tween(220), label = "launch-preview") { current ->
            when (current) {
                BootState.Loading -> LaunchPreview(loading = state == BootState.Loading)
                is BootState.Error -> {
                    val detail = if ((context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0)
                        "\n\n${current.detail}" else ""
                    StatusPanel("Не удалось открыть локальную базу. Попробуйте ещё раз.$detail", retry = boot::retry)
                }
                BootState.Ready -> GuideNavigation(repo, shortcutRequest)
            }
        }
    }
}

@Composable
private fun GuideNavigation(repo: GuideRepository, shortcutRequest: State<ShortcutRequest?> = remember { mutableStateOf(null) }) {
    val nav = rememberNavController()
    // A launcher shortcut (Поиск/Избранное/Недавние) requests one of the top-level tab routes by
    // name; keyed on the request's token so relaunching the same shortcut while the app is already
    // open still navigates. A stale/unknown route string is ignored rather than crashing the nav host.
    LaunchedEffect(shortcutRequest.value?.token) {
        val route = shortcutRequest.value?.route ?: return@LaunchedEffect
        if (Tab.entries.any { it.route == route }) {
            nav.navigate(route) {
                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                launchSingleTop = true
                restoreState = true
            }
        }
    }
    val entry by nav.currentBackStackEntryAsState()
    val destination = entry?.destination
    val galleryOpen = destination?.route?.contains("/gallery/") == true
    val notice by repo.notice.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(notice) { notice?.let { snackbar.showSnackbar(it); repo.clearNotice() } }
    Scaffold(contentWindowInsets = WindowInsets(0, 0, 0, 0), snackbarHost = { SnackbarHost(snackbar) }, bottomBar = {
        if (!galleryOpen) NavigationBar {
            Tab.entries.filter { it != Tab.SEARCH }.forEach { tab ->
                NavigationBarItem(selected = destination?.hierarchy?.any { it.route == tab.route } == true,
                    onClick = {
                        nav.navigate(tab.route) {
                            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }, icon = { Icon(painterResource(tab.icon), contentDescription = null) }, label = { Text(tab.label) })
            }
        }
    }) { padding ->
        NavHost(nav, startDestination = Tab.CATALOG.route,
            modifier = Modifier.padding(padding).consumeWindowInsets(padding),
            enterTransition = { EnterTransition.None }, exitTransition = { ExitTransition.None },
            popEnterTransition = { EnterTransition.None }, popExitTransition = { ExitTransition.None }) {
            navigation(startDestination = "catalog/home", route = "catalog") {
                composable("catalog/home") {
                    OverviewScreen(overviewModel(repo, ""), onSection = { section ->
                        nav.navigate(if (section == MainSection.AMMUNITION) "catalog/section/${section.name}" else "catalog/list/${section.name}")
                    }, onCategory = { category ->
                        nav.navigate("catalog/countries/${MainSection.AMMUNITION.name}?category=${Uri.encode(category)}")
                    }, onGroup = { group ->
                        nav.navigate(if (group == CatalogHierarchy.INITIATION_GROUP) "catalog/initiation" else "catalog/engineering")
                    }, onOpenCard = { id -> nav.navigate("catalog/card/${Uri.encode(id)}") },
                        onUpdate = { nav.navigate("catalog/updates") },
                        onSearch = { nav.navigate(Tab.SEARCH.route) })
                }
                composable("catalog/updates") { UpdateScreen(repo) { nav.popBackStack() } }
                composable("catalog/section/{section}") { backEntry ->
                    val section = backEntry.arguments?.getString("section").orEmpty()
                    OverviewScreen(overviewModel(repo, section), section, onBack = { nav.popBackStack() }, onCategory = { category ->
                        nav.navigate("catalog/countries/$section?category=${Uri.encode(category)}")
                    }, onGroup = { group ->
                        nav.navigate(if (group == CatalogHierarchy.INITIATION_GROUP) "catalog/initiation" else "catalog/engineering")
                    }, onSearch = { nav.navigate(Tab.SEARCH.route) })
                }
                composable("catalog/engineering") {
                    val section = MainSection.AMMUNITION.name
                    OverviewScreen(overviewModel(repo, section), section, onBack = { nav.popBackStack() },
                        onCategory = { category -> nav.navigate("catalog/countries/$section?category=${Uri.encode(category)}") },
                        group = CatalogHierarchy.ENGINEERING_GROUP,
                        onSearch = { nav.navigate(Tab.SEARCH.route) })
                }
                composable("catalog/initiation") {
                    val section = MainSection.AMMUNITION.name
                    OverviewScreen(overviewModel(repo, section), section, onBack = { nav.popBackStack() },
                        onCategory = { category -> nav.navigate("catalog/countries/$section?category=${Uri.encode(category)}") },
                        group = CatalogHierarchy.INITIATION_GROUP,
                        onSearch = { nav.navigate(Tab.SEARCH.route) })
                }
                composable("catalog/countries/{section}?category={category}", arguments = listOf(
                    navArgument("category") { type = NavType.StringType; defaultValue = "" }
                )) { backEntry ->
                    val section = backEntry.arguments?.getString("section").orEmpty()
                    val category = backEntry.arguments?.getString("category").orEmpty()
                    CountryMenuScreen(countryMenuModel(repo), onBack = { nav.popBackStack() },
                        onSearch = { nav.navigate(Tab.SEARCH.route) }) { country ->
                        nav.navigate(readerRoute(CatalogFilter(section = section, category = category, country = country)))
                    }
                }
                composable("catalog/list/{section}?category={category}&country={country}&query={query}&status={status}&photo={photo}", arguments = listOf(
                    navArgument("category") { type = NavType.StringType; defaultValue = "" },
                    navArgument("country") { type = NavType.StringType; defaultValue = "" },
                    navArgument("query") { type = NavType.StringType; defaultValue = "" },
                    navArgument("status") { type = NavType.StringType; defaultValue = "" },
                    navArgument("photo") { type = NavType.StringType; defaultValue = "" }
                )) {
                    val model = catalogModel(repo, CatalogMode.CATALOG)
                    CatalogScreen(model, onBack = { nav.popBackStack() },
                        onRead = { nav.navigate(readerRoute(model.currentFilter())) }) { id ->
                        nav.navigate(readerRoute(model.currentFilter(), id))
                    }
                }
                composable("catalog/reader/{section}?category={category}&country={country}&query={query}&status={status}&photo={photo}&id={id}",
                    arguments = listOf("category", "country", "query", "status", "photo", "id").map { name ->
                        navArgument(name) { type = NavType.StringType; defaultValue = "" }
                    }) { readerEntry ->
                    val model = readerModel(repo)
                    CardReaderScreen(model, repo, onBack = { nav.popBackStack() }, onList = {
                        if (nav.previousBackStackEntry?.destination?.route?.startsWith("catalog/list/") == true) {
                            nav.popBackStack()
                        } else {
                            nav.navigate(listRoute(model.filter)) { popUpTo(readerEntry.destination.id) { inclusive = true } }
                        }
                    }, onImage = { id, index -> nav.navigate("catalog/gallery/${Uri.encode(id)}/$index") })
                }
                cardRoutes("catalog", repo, nav)
            }
            navigation(startDestination = "search_tab/list", route = "search_tab") {
                composable("search_tab/list") {
                    CatalogScreen(catalogModel(repo, CatalogMode.SEARCH), onBack = { nav.popBackStack() }) { id ->
                        nav.navigate("search_tab/card/${Uri.encode(id)}")
                    }
                }
                cardRoutes("search_tab", repo, nav)
            }
            navigation(startDestination = "favorites_tab/list", route = "favorites_tab") {
                composable("favorites_tab/list") {
                    CatalogScreen(catalogModel(repo, CatalogMode.FAVORITES)) { id -> nav.navigate("favorites_tab/card/${Uri.encode(id)}") }
                }
                cardRoutes("favorites_tab", repo, nav)
            }
            navigation(startDestination = "history_tab/list", route = "history_tab") {
                composable("history_tab/list") {
                    CatalogScreen(catalogModel(repo, CatalogMode.HISTORY)) { id -> nav.navigate("history_tab/card/${Uri.encode(id)}") }
                }
                cardRoutes("history_tab", repo, nav)
            }
        }
    }
}

private fun filterArguments(filter: CatalogFilter): String =
    "category=${Uri.encode(filter.category)}&country=${Uri.encode(filter.country)}&query=${Uri.encode(filter.query)}" +
        "&status=${Uri.encode(filter.status)}&photo=${Uri.encode(filter.photo)}"

private fun readerRoute(filter: CatalogFilter, id: String = ""): String =
    "catalog/reader/${Uri.encode(filter.section)}?${filterArguments(filter)}&id=${Uri.encode(id)}"

private fun listRoute(filter: CatalogFilter): String =
    "catalog/list/${Uri.encode(filter.section)}?${filterArguments(filter)}"

private fun NavGraphBuilder.cardRoutes(prefix: String, repo: GuideRepository, nav: NavHostController) {
    composable("$prefix/card/{id}") { entry ->
        val id = entry.arguments?.getString("id").orEmpty()
        DetailScreen(detailModel(repo), onBack = { nav.popBackStack() }) { index ->
            nav.navigate("$prefix/gallery/${Uri.encode(id)}/$index")
        }
    }
    composable("$prefix/gallery/{id}/{index}", arguments = listOf(navArgument("index") { type = NavType.IntType })) { entry ->
        GalleryScreen(galleryModel(repo), entry.arguments?.getInt("index") ?: 0) { nav.popBackStack() }
    }
}

@Composable
private fun overviewModel(repo: GuideRepository, section: String): OverviewViewModel = viewModel(factory = remember(repo, section) {
    viewModelFactory { initializer { OverviewViewModel(repo, section) } }
})

@Composable
private fun catalogModel(repo: GuideRepository, mode: CatalogMode): CatalogViewModel = viewModel(factory = remember(repo, mode) {
    viewModelFactory { initializer { CatalogViewModel(repo, createSavedStateHandle(), mode) } }
})

@Composable
private fun countryMenuModel(repo: GuideRepository): CountryMenuViewModel = viewModel(factory = remember(repo) {
    viewModelFactory { initializer { CountryMenuViewModel(repo, createSavedStateHandle()) } }
})

@Composable
private fun detailModel(repo: GuideRepository): DetailViewModel = viewModel(factory = remember(repo) {
    viewModelFactory { initializer { DetailViewModel(repo, createSavedStateHandle()) } }
})

@Composable
private fun readerModel(repo: GuideRepository): CardReaderViewModel = viewModel(factory = remember(repo) {
    viewModelFactory { initializer { CardReaderViewModel(repo, createSavedStateHandle()) } }
})

@Composable
private fun galleryModel(repo: GuideRepository): GalleryViewModel = viewModel(factory = remember(repo) {
    viewModelFactory { initializer { GalleryViewModel(repo, createSavedStateHandle()) } }
})
