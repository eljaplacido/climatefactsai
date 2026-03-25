"use client";

import { useState, useRef, useEffect } from "react";
import { Share2, Link2, Check, Mail } from "lucide-react";

interface ShareButtonProps {
  articleId: string;
  title: string;
  excerpt?: string;
}

export default function ShareButton({ articleId, title, excerpt }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const shareUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/articles/${articleId}?ref=share`
      : `/articles/${articleId}?ref=share`;

  const shareText = `${title} — CliLens.AI Analysis`;

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    if (showMenu) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showMenu]);

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard not available
    }
    setShowMenu(false);
  }

  function openShareWindow(platform: string) {
    const encodedUrl = encodeURIComponent(shareUrl);
    const encodedText = encodeURIComponent(shareText);

    const urls: Record<string, string> = {
      twitter: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`,
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
      email: `mailto:?subject=${encodedText}&body=${encodeURIComponent(`${excerpt || title}\n\n${shareUrl}`)}`,
    };

    const url = urls[platform];
    if (url) {
      if (platform === "email") {
        window.location.href = url;
      } else {
        window.open(url, "_blank", "width=600,height=400,noopener");
      }
    }
    setShowMenu(false);
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-clilens-primary transition-colors"
        title="Share article"
      >
        {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Share2 className="h-4 w-4" />}
        <span>{copied ? "Copied!" : "Share"}</span>
      </button>

      {showMenu && (
        <div className="absolute top-full mt-2 right-0 z-50 bg-white rounded-xl shadow-xl border border-gray-200 py-2 w-52 animate-in fade-in slide-in-from-top-1 duration-150">
          <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">Share via</p>
          <button
            onClick={handleCopyLink}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center">
              <Link2 className="h-3.5 w-3.5 text-gray-600" />
            </span>
            Copy link
          </button>
          <button
            onClick={() => openShareWindow("twitter")}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
              <span className="text-white font-bold text-xs">𝕏</span>
            </span>
            Post on X
          </button>
          <button
            onClick={() => openShareWindow("linkedin")}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="w-7 h-7 rounded-full bg-[#0A66C2] flex items-center justify-center">
              <span className="text-white font-bold text-xs">in</span>
            </span>
            LinkedIn
          </button>
          <button
            onClick={() => openShareWindow("facebook")}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="w-7 h-7 rounded-full bg-[#1877F2] flex items-center justify-center">
              <span className="text-white font-bold text-xs">f</span>
            </span>
            Facebook
          </button>
          <button
            onClick={() => openShareWindow("email")}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="w-7 h-7 rounded-full bg-emerald-500 flex items-center justify-center">
              <Mail className="h-3.5 w-3.5 text-white" />
            </span>
            Email
          </button>
        </div>
      )}
    </div>
  );
}
