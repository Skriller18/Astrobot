import "@/styles/globals.css";

export const metadata = { title: "MyNaksh", description: "Personalized astrology chat" };

export default function RootLayout({ children }) {
  return <html lang="en"><body>{children}</body></html>;
}
