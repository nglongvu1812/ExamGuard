import { useMemo, useState } from "react";
import katex from "katex";

export interface ContentBlockDTO {
  type: "text" | "math" | "image" | string;
  text?: string;
  latex?: string;
  asset_id?: string;
  alt?: string;
  parse_warning?: boolean;
}

interface RichContentBlocksProps {
  blocks: ContentBlockDTO[];
}

function MathSpan({ latex }: { latex: string }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, {
        throwOnError: false,
        displayMode: false,
        strict: false,
        trust: false,
      });
    } catch {
      return "";
    }
  }, [latex]);

  if (!html) {
    return <code className="font-mono-data rounded bg-amber-50 px-1 text-xs">{latex}</code>;
  }
  return (
    <span
      className="inline-block max-w-full overflow-x-auto align-middle"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export function RichContentBlocks({ blocks }: RichContentBlocksProps) {
  const [zoomAssetUrl, setZoomAssetUrl] = useState<string | null>(null);

  return (
    <div className="space-y-1.5 text-slate-900 leading-relaxed">
      <div className="flex flex-wrap items-baseline gap-1 whitespace-pre-wrap">
        {blocks.map((block, index) => {
          if (block.type === "text") {
            return <span key={index}>{block.text ?? ""}</span>;
          }
          if (block.type === "math") {
            return <MathSpan key={index} latex={block.latex ?? ""} />;
          }
          if (block.type === "image" && block.asset_id) {
            const src = `/api/v1/assets/${block.asset_id}`;
            return (
              <div key={index} className="my-2 w-full">
                <button
                  type="button"
                  onClick={() => setZoomAssetUrl(src)}
                  className="rounded-lg border border-slate-200 bg-white p-1 hover:border-[#1E3A5F]"
                  title="Nhấn để phóng to hình ảnh"
                >
                  <img
                    src={src}
                    alt={block.alt ?? "Hình minh họa câu hỏi"}
                    className="max-h-56 w-auto rounded object-contain"
                  />
                </button>
              </div>
            );
          }
          return null;
        })}
      </div>

      {zoomAssetUrl ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/75 p-4"
          onClick={() => setZoomAssetUrl(null)}
        >
          <div className="max-h-[90vh] max-w-3xl rounded-xl bg-white p-3">
            <img src={zoomAssetUrl} alt="Ảnh phóng to" className="max-h-[82vh] w-auto object-contain" />
            <p className="mt-2 text-center text-xs text-slate-500">Nhấn bất kỳ để đóng</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
