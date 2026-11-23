/** Every metric explained: what it is, how it is calculated, its unit, the period and the source. */
export type Definition = { label: string; what: string; how: string; unit: string; period: string; source: string };

const P = "The date range picked at the top (default: last 3 months), compared with the same number of days just before it.";

export const DEFINITIONS: Record<string, Definition> = {
  revenue: { label: "Revenue", what: "Money taken from orders.", how: "Sum of order totals, including shipping and after discounts. Refunded or cancelled orders are left out.", unit: "Euros (€)", period: P, source: "Shopify orders" },
  orders: { label: "Orders", what: "How many orders were placed.", how: "Count of unique order numbers.", unit: "Orders", period: P, source: "Shopify orders" },
  aov: { label: "Average order value", what: "How much a typical order is worth.", how: "Revenue divided by number of orders.", unit: "Euros (€) per order", period: P, source: "Shopify orders" },
  gift_share: { label: "Gifts", what: "Share of orders bought as a gift.", how: "Orders whose notes mention a gift, divided by all orders.", unit: "% of orders", period: P, source: "Shopify order notes" },
  repeat_rate: { label: "Repeat purchase rate", what: "Share of customers who have bought more than once.", how: "Customers with 2 or more orders, divided by all customers (anonymous ids from hashed emails).", unit: "% of customers", period: "All orders up to the end of the selected period.", source: "Shopify orders" },
  new_customers: { label: "New customers", what: "People who ordered for the first time.", how: "Customers whose first order falls in the period.", unit: "Customers", period: P, source: "Shopify orders" },
  rating: { label: "Average rating", what: "How customers rate your products.", how: "Average of star ratings (1 to 5) on reviews written in the period.", unit: "Stars out of 5", period: P, source: "Product reviews" },
  nps: { label: "NPS", what: "How likely customers are to recommend you.", how: "% of answers scoring 9 or 10, minus % scoring 0 to 6. Ranges from -100 to +100. Needs at least 30 answers.", unit: "Score from -100 to 100", period: "Last 12 months of survey answers.", source: "Survey responses" },
  positive_share: { label: "Positive feedback", what: "Share of feedback that reads as positive.", how: "Feedback marked positive (from the rating, or from the words used when there is no rating), divided by all feedback.", unit: "% of feedback", period: P, source: "Reviews, surveys and messages" },
  volume: { label: "Pieces of feedback", what: "How much feedback arrived.", how: "Count of reviews, survey answers and messages with a date in the period.", unit: "Items", period: P, source: "Reviews, surveys and messages" },
  saves: { label: "Saves per post", what: "How often people save a post to come back to it: the strongest sign that content is useful.", how: "Total saves divided by number of posts published in the period.", unit: "Saves per post", period: P, source: "Instagram posts" },
  er: { label: "Engagement rate", what: "How much people interact with a post compared with how many saw it.", how: "(Likes + comments + saves + shares) divided by reach, averaged across posts. Reach, not impressions or followers, is the denominator.", unit: "% of people reached", period: P, source: "Instagram posts" },
  posts: { label: "Posts", what: "How many posts were published.", how: "Count of posts with a publish date in the period.", unit: "Posts", period: P, source: "Instagram posts" },
  posts_per_week: { label: "Posts per week", what: "How often you post.", how: "Number of posts divided by the number of weeks in the period.", unit: "Posts per week", period: P, source: "Instagram posts" },
  avg_gap: { label: "Average days between posts", what: "The typical wait between one post and the next.", how: "Average number of days between consecutive posts.", unit: "Days", period: P, source: "Instagram posts" },
  weeks_active: { label: "Weeks with a post", what: "How regularly you show up.", how: "Weeks (Monday to Sunday) with at least one post, divided by all weeks in the period.", unit: "% of weeks", period: P, source: "Instagram posts" },
  mission_share: { label: "Mission-led posts", what: "Share of posts about your community and mission, rather than products.", how: "Posts sorted by caption words into topics; mission posts divided by all posts.", unit: "% of posts", period: P, source: "Instagram captions" },
  sessions: { label: "Website visits", what: "How many visits the website had.", how: "Sum of sessions.", unit: "Visits", period: P, source: "Google Analytics" },
  conversion: { label: "Conversion rate", what: "Share of visits that end in a purchase.", how: "Key events (purchases) divided by sessions.", unit: "% of visits", period: P, source: "Google Analytics" },
  web_revenue: { label: "Website revenue", what: "Revenue Google Analytics attributes to the website.", how: "Sum of purchase revenue reported by Google Analytics. It can differ from Shopify because of tracking and consent.", unit: "Euros (€)", period: P, source: "Google Analytics" },
};

export function def(key?: string) {
  return key ? DEFINITIONS[key] : undefined;
}
