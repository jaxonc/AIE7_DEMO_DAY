'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Send } from 'lucide-react'
import Image from 'next/image'

export default function Home() {
  const router = useRouter()
  const [customPrompt, setCustomPrompt] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleCustomPrompt = (e: React.FormEvent) => {
    e.preventDefault()
    if (customPrompt.trim()) {
      setIsLoading(true)
      router.push(`/chat?prompt=${encodeURIComponent(customPrompt.trim())}`)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto max-w-4xl h-screen flex flex-col">
        {/* Header */}
        <header className="p-4">
          <div className="flex items-center space-x-2">
            <div className="p-1 bg-white rounded-lg">
              <Image src="/save-icon.png" alt="S.A.V.E. Icon" width={32} height={32} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-gray-800">S.A.V.E. (Demo Day Prototype)</h1>
              <p className="text-xs text-gray-600">🟢 Online</p>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-4 -mt-32">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-800">S.A.V.E.</h1>
          </div>

          {/* Chat Input */}
          <div className="w-full max-w-2xl">
            <form onSubmit={handleCustomPrompt} className="relative">
              <div className="relative">
                <input
                  type="text"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Ask me anything about food products, UPC codes, or nutrition..."
                  className="w-full px-4 py-3 pr-12 bg-white/70 backdrop-blur-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder-gray-500"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={isLoading || !customPrompt.trim()}
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </button>
              </div>
            </form>
            <p className="text-xs text-gray-500 mt-2 text-center">
              💡 Try: "What are the ingredients for UPC 041548750927?" or "Tell me about hot chips UPC 028400433303"
            </p>
          </div>

          {/* Loading Overlay */}
          {isLoading && (
            <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50">
              <div className="bg-white rounded-lg p-6 shadow-lg">
                <div className="flex items-center space-x-3">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                  <p className="text-gray-700">Preparing your chat session...</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}