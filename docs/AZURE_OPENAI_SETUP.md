# Azure OpenAI Setup Guide

This guide explains how to configure SnapAnalyst to use Azure OpenAI instead of standard OpenAI.

---

## 🎯 Why Azure OpenAI?

Azure OpenAI provides enterprise-grade features:
- ✅ **Enterprise compliance** - Meets corporate security requirements
- ✅ **Data residency** - Keep data in specific regions (EU, US, etc.)
- ✅ **SLA guarantees** - 99.9% uptime with enterprise support
- ✅ **Private endpoints** - VNet integration for secure access
- ✅ **Same models** - GPT-4, GPT-3.5-turbo, and other OpenAI models

---

## 📋 Prerequisites

1. **Azure Subscription** with access to Azure OpenAI Service
2. **Azure OpenAI Resource** created in Azure Portal
3. **Model Deployment** - Deploy a model (e.g., GPT-4, GPT-3.5-turbo)

---

## 🔧 Configuration

### Step 1: Get Azure OpenAI Credentials

From Azure Portal, navigate to your Azure OpenAI resource and collect:

1. **Endpoint URL** - Found in "Keys and Endpoint" section
   - Example: `https://your-resource.openai.azure.com/`

2. **API Key** - Found in "Keys and Endpoint" section
   - Either Key 1 or Key 2

3. **Deployment Name** - The name you gave your model deployment
   - Example: `gpt-4-turbo`, `gpt-35-turbo`

4. **API Version** (optional) - Defaults to `2024-02-15-preview`
   - Check Azure docs for latest version

---

### Step 2: Set Environment Variables

Add these to your `.env` file:

```bash
# LLM Provider Configuration
LLM_PROVIDER=azure_openai

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
AZURE_OPENAI_API_VERSION=2024-02-15-preview  # Optional, has default

# Optional: Specify different models for different tasks
LLM_SQL_MODEL=gpt-4-turbo  # For SQL generation
LLM_KB_MODEL=gpt-35-turbo  # For KB insights (can use cheaper model)
```

---

### Step 3: Restart the Application

```bash
docker-compose restart backend-server frontend-server
```

---

## ✅ Verification

### Check Health Status

```bash
curl http://localhost:8000/api/v1/chat/provider
```

Expected response:
```json
{
  "provider": "azure_openai",
  "sql_model": "gpt-4-turbo",
  "vanna_version": "2.0.1",
  "initialized": true
}
```

### Test SQL Generation

```bash
curl -X POST http://localhost:8000/api/v1/chat/data \
  -H "Content-Type: application/json" \
  -d '{"question": "How many households by state?", "execute": true}'
```

---

## 🔄 Switching Between Providers

You can easily switch between OpenAI and Azure OpenAI by changing the `LLM_PROVIDER` variable:

### Use Standard OpenAI
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Use Azure OpenAI
```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
```

---

## 📊 Model Deployment Recommendations

### For SQL Generation (High Accuracy Required)
- **Recommended:** GPT-4 or GPT-4-turbo
- **Minimum:** GPT-3.5-turbo-16k

### For KB Insights (Cost-Effective)
- **Recommended:** GPT-3.5-turbo
- **Alternative:** GPT-4 (if budget allows)

---

## 🔐 Security Best Practices

1. **Use Managed Identity** (if running in Azure)
   ```python
   # Future enhancement - use DefaultAzureCredential
   from azure.identity import DefaultAzureCredential
   ```

2. **Rotate Keys Regularly** - Use Azure Key Vault for key management

3. **Enable Private Endpoints** - Restrict access to your VNet

4. **Monitor Usage** - Set up Azure Monitor alerts for cost control

---

## 🐛 Troubleshooting

### Error: "Azure endpoint or API key not set"
**Solution:** Verify environment variables are set correctly:
```bash
docker exec backend-server printenv | grep AZURE
```

### Error: "Deployment name not set"
**Solution:** Set `AZURE_OPENAI_DEPLOYMENT_NAME` to match your Azure deployment:
```bash
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
```

### Error: "Resource not found"
**Solution:** Check your endpoint URL format:
- ✅ Correct: `https://your-resource.openai.azure.com/`
- ❌ Wrong: `https://your-resource.openai.azure.com` (missing trailing slash)

### Error: "Invalid API version"
**Solution:** Update to a supported API version:
```bash
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

---

## 💰 Cost Optimization

### Use Different Models for Different Tasks

```bash
# High-accuracy SQL generation
LLM_SQL_MODEL=gpt-4-turbo

# Cost-effective KB insights
LLM_KB_MODEL=gpt-35-turbo
```

### Monitor Token Usage

Check Azure Portal → Your Resource → Metrics → Token Usage

---

## 📚 Additional Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Vanna AI Azure Integration](https://vanna.ai/docs/)
- [OpenAI SDK for Python](https://github.com/openai/openai-python)

---

## 🆘 Support

For issues specific to:
- **Azure OpenAI Service:** Contact Azure Support
- **SnapAnalyst Configuration:** Check application logs
- **Vanna Integration:** See Vanna documentation

---

## 📝 Example Configuration

Complete `.env` example for Azure OpenAI:

```bash
# Environment
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/snapanalyst_db

# LLM Provider - Azure OpenAI
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://mycompany-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=abc123def456...
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Optional: Model-specific settings
LLM_SQL_MODEL=gpt-4-turbo
LLM_KB_MODEL=gpt-35-turbo
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2000

# Vanna Configuration
VANNA_CHROMADB_PATH=./chromadb
VANNA_STORE_USER_QUERIES=false
```

---

**Last Updated:** January 21, 2026
**Version:** 0.1.0
