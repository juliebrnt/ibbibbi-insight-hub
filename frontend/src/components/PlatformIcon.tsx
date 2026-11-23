import {
  siAmazon, siEtsy, siFacebook, siGoogleanalytics, siGoogleforms, siGooglesearchconsole, siHubspot, siInstagram, siLinkedin,
  siMailchimp, siMeta, siShopify, siTiktok, siTrustpilot, siWhatsapp, siWoocommerce, siZendesk,
} from "simple-icons";

const ICONS: Record<string, { path: string; hex: string }> = {
  siAmazon, siEtsy, siFacebook, siGoogleanalytics, siGoogleforms, siGooglesearchconsole, siHubspot, siInstagram, siLinkedin,
  siMailchimp, siMeta, siShopify, siTiktok, siTrustpilot, siWhatsapp, siWoocommerce, siZendesk,
};
const FALLBACK: Record<string, string> = { klaviyo: "K", judgeme: "J", google_reviews: "G", own_files: "≡" };

/** Platform logo from Simple Icons, or a neutral lettered badge when no logo is available. */
export function PlatformIcon({ icon, name, k, size = 36 }: { icon?: string | null; name: string; k?: string; size?: number }) {
  const i = icon ? ICONS[icon] : undefined;
  return (
    <span className="inline-grid shrink-0 place-items-center rounded-xl bg-surface border border-line" style={{ width: size, height: size }} aria-hidden>
      {i ? (
        <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55} fill={i.hex === "000000" ? "rgb(var(--ink))" : `#${i.hex}`}><path d={i.path} /></svg>
      ) : (
        <span className="font-display font-semibold text-ink-2" style={{ fontSize: size * 0.42 }}>{(k && FALLBACK[k]) || name[0]}</span>
      )}
    </span>
  );
}
