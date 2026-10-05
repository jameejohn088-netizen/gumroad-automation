package com.gumroadautomation.data.repository

import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.AutomationRuleDto
import com.gumroadautomation.data.api.dto.AutomationRuleRequest
import com.gumroadautomation.util.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AutomationRepository @Inject constructor(
    private val apiProvider: ApiProvider,
) {
    fun rules(accountId: String?): Flow<ApiResult<List<AutomationRuleDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().listRules(accountId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body().orEmpty()))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load automation rules."))
        }
    }.flowOn(Dispatchers.IO)

    fun saveRule(ruleId: String?, request: AutomationRuleRequest): Flow<ApiResult<AutomationRuleDto>> =
        flow {
            emit(ApiResult.Loading)
            try {
                val api = apiProvider.service()
                val res = if (ruleId == null) api.createRule(request)
                else api.updateRule(ruleId, request)
                if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
                else emit(ApiResult.Error(parseError(res)))
            } catch (e: IOException) {
                emit(ApiResult.Error(networkError(e)))
            } catch (_: Exception) {
                emit(ApiResult.Error("Could not save rule."))
            }
        }.flowOn(Dispatchers.IO)

    fun deleteRule(ruleId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().deleteRule(ruleId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()?.message ?: "Rule deleted"))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not delete rule."))
        }
    }.flowOn(Dispatchers.IO)

    fun toggleRule(rule: AutomationRuleDto, enabled: Boolean): Flow<ApiResult<AutomationRuleDto>> =
        saveRule(
            rule.id,
            AutomationRuleRequest(
                accountId = rule.accountId,
                name = rule.name,
                enabled = enabled,
                trigger = rule.trigger,
                conditions = rule.conditions,
                actions = rule.actions,
                dryRun = rule.dryRun,
            ),
        )
}
