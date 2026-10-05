package com.gumroadautomation.ui.screens.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gumroadautomation.data.api.dto.DashboardDto
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.data.repository.DashboardRepository
import com.gumroadautomation.ui.components.AccountSelector
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.OfflineBanner
import com.gumroadautomation.ui.components.SectionTitle
import com.gumroadautomation.ui.components.StatCard
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.DateUtils
import com.gumroadautomation.util.Money
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val dashboardRepository: DashboardRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    private val _state = MutableStateFlow<ApiResult<DashboardDto>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<DashboardDto>> = _state.asStateFlow()

    private val _accounts = MutableStateFlow<List<GumroadAccountDto>>(emptyList())
    val accounts: StateFlow<List<GumroadAccountDto>> = _accounts.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val accountId = sessionManager.selectedAccountId.first()
            launch {
                accountRepository.accounts().collect { result ->
                    if (result is ApiResult.Success) _accounts.value = result.data
                }
            }
            dashboardRepository.dashboard(accountId).collect { _state.value = it }
        }
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun DashboardScreen(
    onNavigateToAccounts: () -> Unit,
    viewModel: DashboardViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val state by viewModel.state.collectAsState()
    val accounts by viewModel.accounts.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)

    LaunchedEffect(selectedId) { viewModel.refresh() }

    val refreshing = state is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.refresh() })

    androidx.compose.foundation.layout.Box(
        Modifier
            .fillMaxSize()
            .pullRefresh(pullState)
    ) {
        Column(Modifier.fillMaxSize()) {
            AccountSelector(
                accounts = accounts,
                selectedId = selectedId,
                onSelect = { sessionViewModel.selectAccount(it) },
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
            when (val s = state) {
                is ApiResult.Loading -> LoadingView()
                is ApiResult.Error -> {
                    @Suppress("UNCHECKED_CAST")
                    val cached = s.cached as? DashboardDto
                    if (cached != null) {
                        OfflineBanner()
                        DashboardContent(cached, onNavigateToAccounts)
                    } else {
                        ErrorView(s.message, onRetry = { viewModel.refresh() })
                    }
                }
                is ApiResult.Success -> DashboardContent(s.data, onNavigateToAccounts)
            }
        }
        PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
    }
}

@Composable
private fun DashboardContent(
    dashboard: DashboardDto,
    onNavigateToAccounts: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (dashboard.salesCount == 0 && dashboard.productsCount == 0) {
            item {
                EmptyView(
                    message = "No data yet. Connect a Gumroad account and run a sync.",
                    actionLabel = "Manage accounts",
                    onAction = onNavigateToAccounts,
                )
            }
            return@LazyColumn
        }
        item {
            Column(Modifier.padding(horizontal = 16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    StatCard(
                        title = "Revenue",
                        value = Money.format(dashboard.revenueCents, "USD"),
                        modifier = Modifier.weight(1f),
                    )
                    StatCard(
                        title = "Sales",
                        value = dashboard.salesCount.toString(),
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    StatCard(
                        title = "Customers",
                        value = dashboard.customersCount.toString(),
                        modifier = Modifier.weight(1f),
                    )
                    StatCard(
                        title = "Subscribers",
                        value = dashboard.subscribersCount.toString(),
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(8.dp))
                StatCard(
                    title = "Products",
                    value = dashboard.productsCount.toString(),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        if (dashboard.recentSales.isNotEmpty()) {
            item { SectionTitle("Recent sales") }
            items(dashboard.recentSales) { sale ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Row(Modifier.fillMaxWidth()) {
                            Text(
                                sale.productName ?: "Sale",
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                Money.format(sale.amountCents, sale.currency),
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                        Text(
                            text = listOfNotNull(
                                sale.email,
                                sale.createdAt?.let { DateUtils.formatDate(it) },
                            ).joinToString(" • "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        item { Spacer(Modifier.height(16.dp)) }
        item {
            TextButton(onClick = onNavigateToAccounts, modifier = Modifier.fillMaxWidth()) {
                Text("Manage Gumroad accounts")
            }
        }
    }
}
