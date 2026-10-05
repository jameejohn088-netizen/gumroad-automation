package com.gumroadautomation.ui.screens.notifications

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import com.gumroadautomation.data.api.dto.NotificationDto
import com.gumroadautomation.data.repository.OpsRepository
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.DateUtils
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NotificationsViewModel @Inject constructor(
    private val opsRepository: OpsRepository,
) : ViewModel() {

    private val _state =
        MutableStateFlow<ApiResult<List<NotificationDto>>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<List<NotificationDto>>> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            opsRepository.notifications().collect { _state.value = it }
        }
    }

    fun markRead(id: String, onDone: () -> Unit) {
        viewModelScope.launch {
            opsRepository.markNotificationRead(id).collect { result ->
                if (result is ApiResult.Success) {
                    refresh()
                    onDone()
                }
            }
        }
    }

    fun markAllRead() {
        viewModelScope.launch {
            opsRepository.markAllNotificationsRead().collect { result ->
                if (result is ApiResult.Success) refresh()
            }
        }
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun NotificationsScreen(
    viewModel: NotificationsViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state) {
        // Keep the top-bar badge in sync.
        sessionViewModel.refreshUnread()
    }

    val refreshing = state is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.refresh() })

    androidx.compose.foundation.layout.Box(
        Modifier
            .fillMaxSize()
            .pullRefresh(pullState)
    ) {
        Column(Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                OutlinedButton(onClick = { viewModel.markAllRead() }) {
                    Text("Mark all read")
                }
            }
            when (val s = state) {
                is ApiResult.Loading -> LoadingView()
                is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.refresh() })
                is ApiResult.Success -> {
                    if (s.data.isEmpty()) {
                        EmptyView("No notifications.")
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items(s.data, key = { it.id }) { notification ->
                                Card(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 16.dp),
                                    colors = if (!notification.read) {
                                        CardDefaults.cardColors(
                                            containerColor = MaterialTheme.colorScheme.primaryContainer
                                        )
                                    } else CardDefaults.cardColors(),
                                    onClick = {
                                        if (!notification.read) {
                                            viewModel.markRead(notification.id) {
                                                sessionViewModel.refreshUnread()
                                            }
                                        }
                                    },
                                ) {
                                    Column(Modifier.padding(12.dp)) {
                                        Text(
                                            notification.title,
                                            style = MaterialTheme.typography.bodyLarge,
                                            fontWeight = if (notification.read) FontWeight.Normal
                                            else FontWeight.Bold,
                                        )
                                        notification.body?.let {
                                            Text(
                                                it,
                                                style = MaterialTheme.typography.bodyMedium,
                                            )
                                        }
                                        notification.createdAt?.let {
                                            Text(
                                                DateUtils.formatDateTime(it),
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
    }
}
