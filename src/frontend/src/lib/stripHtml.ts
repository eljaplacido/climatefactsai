// Defensive client-side HTML strip for fields where the backend
// cleaner may have missed (legacy RSS-summary rows, image-only WordPress
// content, etc.). The backend's shared.html_cleaner is the source of
// truth for newly-ingested rows; this is a belt-and-braces fallback so
// the rendered UI is never polluted with raw `<figure>` / `<img>` /
// "appeared first on Y" markup.
//
// Used by ArticleDetailTabs (excerpt + fullText) and FullArticlePanel
// (extracted_text). Mirrors the in-file stripHtml in FullArticlePanel
// that pre-dated this util — now both call the shared version.

export function stripHtml(text: string | null | undefined): string {
  if (!text) return "";
  if (!/<[a-zA-Z!/]/.test(text)) return text;
  let out = text.replace(/<(script|style|iframe)[\s\S]*?<\/\1>/gi, "");
  out = out.replace(/<(img|br|hr|input|source|track|meta|link)[^>]*\/?>/gi, "\n");
  out = out.replace(/<\/(p|div|section|article|h[1-6]|li|tr|figure|figcaption)>/gi, "\n\n");
  out = out.replace(/<[^>]+>/g, " ");
  out = out
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  out = out.replace(/\n*The post\s+[\s\S]+?\s+appeared first on\s+[\s\S]+?\.\s*$/i, "");
  out = out.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  return out;
}
