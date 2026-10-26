import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, Send, Sparkles, Bot, User as UserIcon,
  Play, CheckCircle, CheckCircle2, Clock, AlertCircle, ArrowRight, RefreshCw,
  ExternalLink, Layers, ShieldCheck, ShieldAlert, Zap, Paperclip, X, FileText,
  Download, Maximize2, Copy, Check, Plus, History, Trash2
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  chatApi,
  uploadsApi,
  approvalsApi,
  type ChatResponse,
  type ChatSuggestion,
  type ChatApprovalCard,
  type StreamChatEvent,
  type ConversationItem,
  type ChatMessageItem,
} from '../lib/api'
import { SectionHeader, StatusBadge } from '../components/ui'
import { MarkdownView } from '../components/MarkdownView'

interface Message {
  id: string
  sender: 'user' | 'assistant'
  text: string
  timestamp: string
  isTask?: boolean
  orchestrationId?: string
  status?: string
  tasks?: Array<{
    id: string
    name: string
    status: string
    agent: string
  }>
  sources?: Array<{ name: string; id: string }>
  attachedFileName?: string
  requiresApproval?: boolean
  approval?: ChatApprovalCard
  approvalStatus?: 'PENDING' | 'APPROVED' | 'REJECTED'
  imageUrl?: string
  imageMeta?: {
    image_url?: string
    prompt: string
    enhanced_prompt?: string
    width?: number
    height?: number
    seed?: number
    model?: string
    style?: string
  }
}

const DEFAULT_WELCOME_MSG: Message = {
  id: 'welcome',
  sender: 'assistant',
  text: "👋 **Hello! I am your Enterprise Multi-Agent AI Assistant.**\n\nAsk me anything in real time — questions, technical explanations, summaries, code, or enterprise tasks. You can also attach files (**📎 CSV, Excel, PDF, Word, TXT**) for instant analysis or assign workflows with strict human-in-the-loop approval governance for external side effects.",
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
}

const mapDbMessage = (dbMsg: ChatMessageItem): Message => {
  const meta = dbMsg.metadata || {}
  return {
    id: dbMsg.id,
    sender: dbMsg.sender,
    text: dbMsg.content,
    timestamp: dbMsg.created_at ? new Date(dbMsg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
    attachedFileName: meta.attached_filename,
    isTask: meta.is_task,
    orchestrationId: meta.orchestration_id,
    sources: meta.sources,
    imageUrl: meta.image?.image_url,
    imageMeta: meta.image,
    tasks: meta.tasks,
  }
}

export default function ChatAssistantPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([DEFAULT_WELCOME_MSG])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false)
  const [loadingConv, setLoadingConv] = useState(false)

  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<ChatSuggestion[]>([])
  const [mode, setMode] = useState<'auto' | 'task' | 'chat'>('auto')
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [copiedPrompt, setCopiedPrompt] = useState<string | null>(null)
  const [attachedFileId, setAttachedFileId] = useState<string | null>(null)
  const [attachedFileName, setAttachedFileName] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const loadConversations = async () => {
    try {
      const res = await chatApi.listConversations('chat_assistant')
      if (res?.conversations) {
        setConversations(res.conversations)
      }
    } catch {}
  }

  const loadConversationHistory = async (convId: string) => {
    setLoadingConv(true)
    try {
      const res = await chatApi.getConversation(convId)
      if (res?.conversation) {
        setActiveConvId(res.conversation.id)
        localStorage.setItem('orchestrai_active_chat_conv_id', res.conversation.id)
        if (res.conversation.messages && res.conversation.messages.length > 0) {
          setMessages(res.conversation.messages.map(mapDbMessage))
        } else {
          setMessages([DEFAULT_WELCOME_MSG])
        }
      }
    } catch (e) {
      console.warn('Failed to load conversation history:', e)
    } finally {
      setLoadingConv(false)
    }
  }

  useEffect(() => {
    chatApi.suggestions()
      .then(res => {
        if (res?.suggestions) setSuggestions(res.suggestions)
      })
      .catch(() => {})

    loadConversations()
    const savedConvId = localStorage.getItem('orchestrai_active_chat_conv_id')
    if (savedConvId) {
      loadConversationHistory(savedConvId)
    }
  }, [])

  const handleNewChat = async () => {
    try {
      const res = await chatApi.createConversation('chat_assistant', 'New Conversation')
      if (res?.conversation) {
        setActiveConvId(res.conversation.id)
        localStorage.setItem('orchestrai_active_chat_conv_id', res.conversation.id)
        setMessages([DEFAULT_WELCOME_MSG])
        setShowHistoryDrawer(false)
        loadConversations()
      }
    } catch {
      setActiveConvId(null)
      localStorage.removeItem('orchestrai_active_chat_conv_id')
      setMessages([DEFAULT_WELCOME_MSG])
      setShowHistoryDrawer(false)
    }
  }

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation()
    try {
      await chatApi.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (activeConvId === convId) {
        handleNewChat()
      }
    } catch (err: any) {
      alert(`Failed to delete conversation: ${err.message || err}`)
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingFile(true)
    try {
      const res = await uploadsApi.upload(file)
      setAttachedFileId(res.file_id)
      setAttachedFileName(res.filename)
    } catch (err: any) {
      alert(err.message || 'File upload failed.')
    } finally {
      setUploadingFile(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleApproveAction = async (msgId: string, approvalId: string) => {
    try {
      await approvalsApi.approve(approvalId, 'Approved via Chat Assistant')
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        return {
          ...m,
          approvalStatus: 'APPROVED',
          approval: m.approval ? { ...m.approval, status: 'APPROVED' } : undefined,
          text: m.text + '\n\n> 🛡️ **Action Approved**: The external operation was authorized and dispatched.',
        }
      }))
    } catch (err: any) {
      alert(`Approval failed: ${err.message || err}`)
    }
  }

  const handleRejectAction = async (msgId: string, approvalId: string) => {
    try {
      await approvalsApi.reject(approvalId, 'Rejected by user in Chat Assistant')
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        return {
          ...m,
          approvalStatus: 'REJECTED',
          approval: m.approval ? { ...m.approval, status: 'REJECTED' } : undefined,
          text: m.text + '\n\n> 🛑 **Action Rejected**: Execution cancelled safely to protect system integrity.',
        }
      }))
    } catch (err: any) {
      alert(`Rejection failed: ${err.message || err}`)
    }
  }

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim()
    if ((!text && !attachedFileId) || loading) return

    const messageText = text || `Please inspect and analyze the attached file: ${attachedFileName}`
    const currentFileId = attachedFileId
    const currentFileName = attachedFileName

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: messageText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachedFileName: currentFileName || undefined,
    }

    const asstId = `asst-${Date.now()}`
    const placeholderMsg: Message = {
      id: asstId,
      sender: 'assistant',
      text: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages(prev => [...prev, userMsg, placeholderMsg])
    if (!textToSend) {
      setInput('')
      setAttachedFileId(null)
      setAttachedFileName(null)
    }
    setLoading(true)

    try {
      const context: Record<string, any> = {}
      if (currentFileId) {
        context.file_id = currentFileId
        context.filename = currentFileName
      }

      const historyPayload = messages
        .filter(m => m.id !== 'welcome' && m.id !== asstId && m.text && m.text.trim())
        .slice(-8)
        .map(m => ({
          role: m.sender === 'user' ? ('user' as const) : ('assistant' as const),
          content: m.text,
        }))

      let accumulated = ''
      const res = await chatApi.streamChat(
        messageText,
        mode,
        context,
        (evt: StreamChatEvent) => {
          if (evt.event_type === 'node.started' || evt.event_type === 'node.completed') {
            setMessages(prev => prev.map(m => {
              if (m.id !== asstId) return m
              const existingTasks = m.tasks ? [...m.tasks] : []
              const agentName = evt.data?.agent_type || evt.data?.task_name || 'Agent'
              const taskIdx = existingTasks.findIndex(t => t.name === agentName || t.id === evt.data?.task_id)
              if (taskIdx >= 0) {
                existingTasks[taskIdx].status = evt.event_type === 'node.completed' ? 'COMPLETED' : 'RUNNING'
              } else {
                existingTasks.push({
                  id: evt.data?.task_id || `t-${Date.now()}`,
                  name: agentName,
                  status: evt.event_type === 'node.completed' ? 'COMPLETED' : 'RUNNING',
                  agent: evt.data?.agent_type || agentName,
                })
              }
              return { ...m, isTask: true, tasks: existingTasks }
            }))
          } else if (evt.event_type === 'approval.created' || evt.event_type === 'node.waiting_approval') {
            const appr = evt.data
            setMessages(prev => prev.map(m => {
              if (m.id !== asstId) return m
              return {
                ...m,
                requiresApproval: true,
                approvalStatus: 'PENDING',
                approval: {
                  approval_id: appr?.approval_id || appr?.id,
                  workflow_id: appr?.workflow_id,
                  execution_id: appr?.execution_id,
                  node_id: appr?.node_id,
                  agent_id: appr?.agent_id,
                  agent_type: appr?.agent_type,
                  action_type: appr?.action_type || appr?.requested_action,
                  target: appr?.target,
                  parameters_summary: appr?.parameters_summary,
                  risk_level: appr?.risk_level || 'high',
                  status: 'PENDING',
                }
              }
            }))
          } else if (evt.event_type === 'assistant.image') {
            const imgData = evt.data
            setMessages(prev => prev.map(m => {
              if (m.id !== asstId) return m
              return {
                ...m,
                imageUrl: imgData?.image_url,
                imageMeta: imgData,
              }
            }))
          }
        },
        (delta: string) => {
          accumulated += delta
          setMessages(prev => prev.map(m => (m.id === asstId ? { ...m, text: accumulated } : m)))
        },
        historyPayload,
        activeConvId || undefined
      )

      if (res.conversation_id) {
        setActiveConvId(res.conversation_id)
        localStorage.setItem('orchestrai_active_chat_conv_id', res.conversation_id)
        loadConversations()
      }

      const rawText = typeof (res.response || accumulated || '') === 'string'
        ? (res.response || accumulated || '')
        : JSON.stringify(res.response || accumulated || '', null, 2)
      
      const mdImgMatch = rawText.match(/!\[.*?\]\((https:\/\/image\.pollinations\.ai\/[^\s\)]+)\)/)
      const resolvedImgUrl = res.image?.image_url || (mdImgMatch ? mdImgMatch[1] : undefined)

      setMessages(prev => prev.map(m => {
        if (m.id !== asstId) return m
        return {
          ...m,
          text: rawText || m.text,
          isTask: res.is_task || m.isTask,
          orchestrationId: res.orchestration_id || m.orchestrationId,
          status: res.status || m.status,
          sources: res.sources || m.sources,
          requiresApproval: res.requires_approval ?? m.requiresApproval,
          approval: res.approval ?? m.approval,
          imageUrl: resolvedImgUrl || m.imageUrl,
          imageMeta: res.image || m.imageMeta,
        }
      }))
    } catch (err: any) {
      setMessages(prev => prev.map(m => {
        if (m.id !== asstId) return m
        return {
          ...m,
          text: m.text ? m.text + `\n\n⚠️ **Stream error:** ${err.message}` : `⚠️ **Error:** ${err.message || 'Unable to communicate with the Assistant.'}`,
        }
      }))
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 56px)', background: 'var(--surface-0)' }}>
      {/* Top Header */}
      <div style={{
        padding: '16px 24px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--surface-1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(99,102,241,0.35)',
            }}>
              <Sparkles size={16} color="white" />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Chat Assistant
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                Natural Language Enterprise Conversation & Automated Task Delegation
              </p>
            </div>
          </div>
        </div>

        {/* Header Actions & Mode Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={handleNewChat}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
              background: 'var(--surface-2)',
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              transition: 'all 0.2s',
            }}
            title="Start a fresh chat thread"
          >
            <Plus size={14} color="var(--primary)" />
            <span>New Chat</span>
          </button>

          <button
            onClick={() => setShowHistoryDrawer(prev => !prev)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              border: showHistoryDrawer ? '1px solid var(--primary)' : '1px solid var(--border-subtle)',
              cursor: 'pointer',
              background: showHistoryDrawer ? 'rgba(99, 102, 241, 0.15)' : 'var(--surface-2)',
              color: showHistoryDrawer ? 'var(--primary)' : 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              transition: 'all 0.2s',
            }}
            title="View persistent chat threads"
          >
            <History size={14} />
            <span>History ({conversations.length})</span>
          </button>

          {/* Mode Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--surface-2)', padding: 3, borderRadius: 8 }}>
            <button
              onClick={() => setMode('auto')}
              style={{
                padding: '5px 10px',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: mode === 'auto' ? 'var(--primary)' : 'transparent',
                color: mode === 'auto' ? 'white' : 'var(--text-muted)',
                transition: 'all 0.2s',
              }}
            >
              Auto
            </button>
            <button
              onClick={() => setMode('task')}
              style={{
                padding: '5px 10px',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: mode === 'task' ? 'var(--primary)' : 'transparent',
                color: mode === 'task' ? 'white' : 'var(--text-muted)',
                transition: 'all 0.2s',
              }}
            >
              Force Task
            </button>
            <button
              onClick={() => setMode('chat')}
              style={{
                padding: '5px 10px',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: mode === 'chat' ? 'var(--primary)' : 'transparent',
                color: mode === 'chat' ? 'white' : 'var(--text-muted)',
                transition: 'all 0.2s',
              }}
            >
              Chat Only
            </button>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
        <AnimatePresence>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              style={{
                display: 'flex',
                gap: 12,
                marginBottom: 20,
                flexDirection: m.sender === 'user' ? 'row-reverse' : 'row',
              }}
            >
              {/* Avatar */}
              <div style={{
                width: 34, height: 34, borderRadius: '50%',
                background: m.sender === 'user'
                  ? 'var(--surface-3)'
                  : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
                color: m.sender === 'user' ? 'var(--text-secondary)' : 'white',
              }}>
                {m.sender === 'user' ? <UserIcon size={16} /> : <Bot size={18} />}
              </div>

              {/* Message Content */}
              <div style={{
                maxWidth: '80%',
                background: m.sender === 'user' ? 'var(--primary)' : 'var(--surface-1)',
                color: m.sender === 'user' ? 'white' : 'var(--text-primary)',
                border: m.sender === 'user' ? 'none' : '1px solid var(--border-subtle)',
                borderRadius: 14,
                padding: '14px 18px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              }}>
                {m.attachedFileName && (
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 8px',
                    borderRadius: 6,
                    background: m.sender === 'user' ? 'rgba(255,255,255,0.2)' : 'var(--surface-2)',
                    color: m.sender === 'user' ? 'white' : 'var(--primary)',
                    fontSize: 11,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}>
                    <Paperclip size={12} />
                    <span>{m.attachedFileName}</span>
                  </div>
                )}
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                  {m.sender === 'assistant' ? (
                    m.text ? (
                      <MarkdownView content={typeof m.text === 'string' ? m.text : JSON.stringify(m.text, null, 2)} />
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', padding: '6px 0' }}>
                        <RefreshCw size={14} className="animate-spin" />
                        <span style={{ fontSize: 13, fontStyle: 'italic' }}>Thinking & responding in real time…</span>
                      </div>
                    )
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {typeof m.text === 'string' ? m.text : JSON.stringify(m.text, null, 2)}
                    </div>
                  )}
                </div>

                {/* AI Visual Asset Showcase */}
                {(m.imageUrl || m.imageMeta?.image_url) && (
                  <div style={{
                    marginTop: 14,
                    borderRadius: 12,
                    overflow: 'hidden',
                    border: '1px solid var(--border-subtle)',
                    background: 'var(--surface-0)',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
                  }}>
                    <div style={{ position: 'relative', width: '100%', maxHeight: 420, overflow: 'hidden', background: '#0f172a' }}>
                      <img
                        src={m.imageUrl || m.imageMeta?.image_url}
                        alt={m.imageMeta?.prompt || 'Generated Visual'}
                        style={{ width: '100%', height: 'auto', maxHeight: 420, objectFit: 'contain', display: 'block', cursor: 'pointer' }}
                        onClick={() => setPreviewImage(m.imageUrl || m.imageMeta?.image_url || null)}
                      />
                      <button
                        onClick={() => setPreviewImage(m.imageUrl || m.imageMeta?.image_url || null)}
                        style={{
                          position: 'absolute', top: 10, right: 10,
                          background: 'rgba(0,0,0,0.6)', border: 'none', borderRadius: 6,
                          padding: 6, color: 'white', cursor: 'pointer',
                          backdropFilter: 'blur(4px)',
                        }}
                        title="View Fullscreen"
                      >
                        <Maximize2 size={16} />
                      </button>
                    </div>
                    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                      <div style={{ flex: 1, minWidth: 200 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          Flux.1 Latent Diffusion • {m.imageMeta?.width || 1024}x{m.imageMeta?.height || 1024}px
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          "{m.imageMeta?.prompt || 'Visual Asset'}"
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                          onClick={() => {
                            if (m.imageMeta?.prompt) {
                              navigator.clipboard.writeText(m.imageMeta.prompt)
                              setCopiedPrompt(m.id)
                              setTimeout(() => setCopiedPrompt(null), 2000)
                            }
                          }}
                          style={{
                            padding: '6px 10px', borderRadius: 6,
                            background: 'var(--surface-2)', border: '1px solid var(--border-subtle)',
                            color: 'var(--text-primary)', fontSize: 11, fontWeight: 600,
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          {copiedPrompt === m.id ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                          <span>{copiedPrompt === m.id ? 'Copied' : 'Prompt'}</span>
                        </button>
                        <a
                          href={m.imageUrl || m.imageMeta?.image_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          download="ai_generated_image.jpg"
                          style={{
                            padding: '6px 12px', borderRadius: 6,
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            color: 'white', fontSize: 11, fontWeight: 600, textDecoration: 'none',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          <Download size={12} />
                          <span>Download</span>
                        </a>
                      </div>
                    </div>
                  </div>
                )}

                {/* Verified Real-time Citations */}
                {m.sources && m.sources.length > 0 && (
                  <div style={{
                    marginTop: 10,
                    paddingTop: 8,
                    borderTop: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: 6,
                  }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>
                      Verified Sources:
                    </span>
                    {m.sources.map((s, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: 'var(--surface-2)',
                          color: 'var(--primary)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        🌐 {s.name}
                      </span>
                    ))}
                  </div>
                )}

                {/* If Assistant Generated an Orchestration Task */}
                {m.isTask && (
                  <div style={{
                    marginTop: 14,
                    padding: 12,
                    borderRadius: 8,
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border-subtle)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: 'var(--primary)' }}>
                        <Zap size={14} color="#10b981" /> Real-Time Multi-Agent Execution
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {m.requiresApproval ? (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 12,
                            background: 'rgba(234, 179, 8, 0.15)',
                            color: '#eab308',
                            border: '1px solid rgba(234, 179, 8, 0.3)',
                          }}>
                            <Clock size={11} /> Awaiting Approval
                          </span>
                        ) : (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 12,
                            background: 'rgba(99, 102, 241, 0.15)',
                            color: '#6366f1',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                          }}>
                            <ShieldCheck size={11} /> Verified Execution
                          </span>
                        )}
                        {m.status && (
                          <StatusBadge
                            status={m.status === 'COMPLETED' ? 'success' : m.status === 'RUNNING' ? 'running' : 'info'}
                            label={m.status}
                          />
                        )}
                      </div>
                    </div>

                    {/* Interactive Inline Approval Request Card */}
                    {m.requiresApproval && m.approval && (
                      <div style={{
                        marginBottom: 12,
                        padding: 12,
                        borderRadius: 8,
                        background: 'rgba(234, 179, 8, 0.08)',
                        border: '1px solid rgba(234, 179, 8, 0.3)',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: '#eab308' }}>
                            <ShieldAlert size={14} /> Action Requires Authorization
                          </div>
                          <span style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 6px',
                            borderRadius: 4,
                            background: m.approval.risk_level === 'high' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                            color: m.approval.risk_level === 'high' ? '#ef4444' : '#eab308',
                            textTransform: 'uppercase',
                          }}>
                            {m.approval.risk_level || 'HIGH RISK'}
                          </span>
                        </div>

                        <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 6 }}>
                          <strong>Action:</strong> {m.approval.action_type || 'External side-effect execution'}
                        </div>
                        {m.approval.target && (
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            <strong>Target:</strong> <code>{m.approval.target}</code>
                          </div>
                        )}
                        {m.approval.parameters_summary && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, background: 'var(--surface-0)', padding: 6, borderRadius: 4 }}>
                            <pre style={{ margin: 0, fontSize: 10, whiteSpace: 'pre-wrap' }}>
                              {JSON.stringify(m.approval.parameters_summary, null, 2)}
                            </pre>
                          </div>
                        )}

                        {(!m.approvalStatus || m.approvalStatus === 'PENDING') && (
                          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                            <button
                              onClick={() => handleApproveAction(m.id, m.approval!.approval_id)}
                              className="btn btn-sm"
                              style={{
                                background: '#10b981',
                                color: 'white',
                                border: 'none',
                                fontSize: 11,
                                fontWeight: 600,
                                padding: '6px 14px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                cursor: 'pointer',
                              }}
                            >
                              <CheckCircle2 size={13} /> Approve & Dispatch
                            </button>
                            <button
                              onClick={() => handleRejectAction(m.id, m.approval!.approval_id)}
                              className="btn btn-sm"
                              style={{
                                background: '#ef4444',
                                color: 'white',
                                border: 'none',
                                fontSize: 11,
                                fontWeight: 600,
                                padding: '6px 14px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                cursor: 'pointer',
                              }}
                            >
                              <X size={13} /> Reject Action
                            </button>
                          </div>
                        )}

                        {m.approvalStatus === 'APPROVED' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#10b981', fontWeight: 600, marginTop: 6 }}>
                            <CheckCircle2 size={14} /> Action Authorized & Resumed
                          </div>
                        )}

                        {m.approvalStatus === 'REJECTED' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#ef4444', fontWeight: 600, marginTop: 6 }}>
                            <X size={14} /> Action Rejected by User
                          </div>
                        )}
                      </div>
                    )}

                    {m.tasks && m.tasks.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                        {m.tasks.map(t => (
                          <div
                            key={t.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              fontSize: 12,
                              padding: '6px 10px',
                              borderRadius: 6,
                              background: 'var(--surface-1)',
                              border: '1px solid var(--border-subtle)',
                            }}
                          >
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t.agent}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button
                        onClick={() => navigate('/tasks')}
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: 11, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        <Play size={12} /> Open in Task Manager
                      </button>
                      <button
                        onClick={() => navigate('/executions')}
                        className="btn btn-ghost btn-sm"
                        style={{ fontSize: 11, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        <ExternalLink size={12} /> View Execution Logs
                      </button>
                    </div>
                  </div>
                )}

                <div style={{
                  fontSize: 10,
                  color: m.sender === 'user' ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)',
                  marginTop: 6,
                  textAlign: 'right',
                }}>
                  {m.timestamp}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions Drawer */}
      {suggestions.length > 0 && messages.length <= 2 && (
        <div style={{
          padding: '10px 20px',
          maxWidth: 900,
          width: '100%',
          margin: '0 auto',
          display: 'flex',
          gap: 8,
          overflowX: 'auto',
        }}>
          {suggestions.slice(0, 3).map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(s.prompt)}
              style={{
                padding: '6px 12px',
                borderRadius: 20,
                background: 'var(--surface-2)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontSize: 11,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.2s',
              }}
            >
              <Sparkles size={12} color="var(--primary)" />
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Input Box Footer */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--border-subtle)',
        background: 'var(--surface-1)',
      }}>
        <div style={{
          maxWidth: 900,
          width: '100%',
          margin: '0 auto',
        }}>
          {/* Active File Attachment Chip */}
          {attachedFileName && (
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 8,
              padding: '5px 12px',
              borderRadius: 6,
              background: 'rgba(99, 102, 241, 0.12)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              fontSize: 12,
              color: 'var(--primary)',
            }}>
              <Paperclip size={13} />
              <span style={{ fontWeight: 600 }}>{attachedFileName}</span>
              <button
                type="button"
                onClick={() => {
                  setAttachedFileId(null)
                  setAttachedFileName(null)
                }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0 }}
              >
                <X size={13} />
              </button>
            </div>
          )}

          <div style={{
            display: 'flex',
            gap: 10,
            alignItems: 'flex-end',
          }}>
            {/* Hidden File Input */}
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
              accept=".csv,.xlsx,.xls,.pdf,.docx,.doc,.txt,.json"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingFile || loading}
              className="btn btn-secondary"
              title="Attach File (CSV, Excel, PDF, Word, TXT)"
              style={{
                padding: '12px 14px',
                borderRadius: 10,
                height: 48,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {uploadingFile ? <RefreshCw size={16} className="animate-spin" /> : <Paperclip size={16} />}
            </button>

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={attachedFileName ? `Ask anything about ${attachedFileName} (e.g. 'Analyze statistics', 'Summarize key points')...` : "Type your message, ask questions, or describe an automation goal..."}
              rows={2}
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 10,
                background: 'var(--surface-0)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontSize: 13,
                resize: 'none',
                outline: 'none',
                lineHeight: 1.4,
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={(!input.trim() && !attachedFileId) || loading}
              className="btn btn-primary"
              style={{
                padding: '12px 18px',
                borderRadius: 10,
                height: 48,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                flexShrink: 0,
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-out History Drawer */}
      <AnimatePresence>
        {showHistoryDrawer && (
          <div
            onClick={() => setShowHistoryDrawer(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 1000,
              background: 'rgba(0,0,0,0.6)',
              backdropFilter: 'blur(3px)',
              display: 'flex',
              justifyContent: 'flex-end',
            }}
          >
            <motion.div
              initial={{ x: 380, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 380, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 250 }}
              onClick={e => e.stopPropagation()}
              style={{
                width: 380,
                maxWidth: '90vw',
                height: '100%',
                background: 'var(--surface-1)',
                borderLeft: '1px solid var(--border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '-8px 0 24px rgba(0,0,0,0.3)',
              }}
            >
              <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <History size={18} color="var(--primary)" />
                  <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Chat History</span>
                </div>
                <button
                  onClick={() => setShowHistoryDrawer(false)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 4,
                  }}
                >
                  <X size={18} />
                </button>
              </div>

              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                <button
                  onClick={handleNewChat}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    background: 'var(--primary)',
                    color: 'white',
                    border: 'none',
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                  }}
                >
                  <Plus size={16} />
                  <span>Start New Chat</span>
                </button>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
                {conversations.length === 0 ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, marginTop: 40 }}>
                    No saved conversations yet.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {conversations.map(c => {
                      const isActive = activeConvId === c.id
                      return (
                        <div
                          key={c.id}
                          onClick={() => {
                            loadConversationHistory(c.id)
                            setShowHistoryDrawer(false)
                          }}
                          style={{
                            padding: '12px 14px',
                            borderRadius: 10,
                            background: isActive ? 'rgba(99, 102, 241, 0.12)' : 'var(--surface-2)',
                            border: isActive ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid var(--border-subtle)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'flex-start',
                            justifyContent: 'space-between',
                            gap: 10,
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontWeight: 600,
                              fontSize: 13,
                              color: isActive ? 'var(--primary)' : 'var(--text-primary)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}>
                              {c.title || 'Untitled Thread'}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                              <Clock size={11} />
                              <span>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : ''}</span>
                              {c.message_count != null && <span>• {c.message_count} msgs</span>}
                            </div>
                          </div>
                          <button
                            onClick={(e) => handleDeleteConversation(e, c.id)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-muted)',
                              cursor: 'pointer',
                              padding: 4,
                              borderRadius: 4,
                            }}
                            title="Delete thread"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Fullscreen Lightbox Image Modal */}
      {previewImage && (
        <div
          onClick={() => setPreviewImage(null)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.88)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 9999, padding: 24, cursor: 'zoom-out',
            backdropFilter: 'blur(8px)',
          }}
        >
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setPreviewImage(null)}
              style={{
                position: 'absolute', top: -38, right: 0,
                background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 6,
                color: 'white', padding: '6px 12px',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600,
              }}
            >
              <X size={16} /> Close
            </button>
            <img
              src={previewImage}
              alt="Fullscreen Preview"
              style={{
                maxWidth: '90vw', maxHeight: '85vh',
                objectFit: 'contain', borderRadius: 12,
                boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
                border: '1px solid rgba(255,255,255,0.1)',
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
