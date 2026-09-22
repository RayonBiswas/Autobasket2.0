import { useEffect, useState } from "react";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";

// Settings card: link the household to the Telegram bot so "shall we order?" asks arrive on the phone.
function TelegramCard() {
  const notify = useToast();
  const [state, setState] = useState(null);
  const [link, setLink] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    API.get("/telegram/link").then((r) => alive && setState(r.data)).catch(() => alive && setState({ enabled: false }));
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => { alive = false; clearInterval(id); };
  }, [tick]);

  const connect = async () => {
    try {
      const res = await API.post("/telegram/link");
      setLink(res.data);
    } catch (err) {
      notify(errorText(err, "We couldn't start the link."), "error");
    }
  };

  const disconnect = async () => {
    try {
      await API.delete("/telegram/link");
      setLink(null);
      setTick((t) => t + 1);
      notify("Telegram disconnected. Alerts stay in the app.");
    } catch (err) {
      notify(errorText(err, "We couldn't disconnect."), "error");
    }
  };

  if (!state) return null;

  return (
    <section>
      <div className="section-title"><h2>Alerts on your phone</h2><span>Telegram, free and instant</span></div>
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {!state.enabled && (
          <p className="muted">Telegram alerts aren't switched on for this server yet. You'll still see every ask here in the app.</p>
        )}
        {state.enabled && state.connected && (
          <>
            <p>Connected. When something runs low you'll get the three best offers with Yes buttons.</p>
            <div><button className="btn" onClick={disconnect}>Disconnect</button></div>
          </>
        )}
        {state.enabled && !state.connected && !link && (
          <>
            <p className="muted">Get "milk runs out tomorrow, order from Sharma for ₹58?" on Telegram and answer with one tap.</p>
            <div><button className="btn btn-primary" onClick={connect}>Connect Telegram</button></div>
          </>
        )}
        {state.enabled && !state.connected && link && (
          <>
            <p>Open the bot and press Start. Once it replies, this card updates by itself.</p>
            {link.url && <a className="btn btn-primary" href={link.url} target="_blank" rel="noreferrer">Open @{state.bot_username}</a>}
            <p className="small muted">Or send the bot <code>/start {link.code}</code> yourself.</p>
          </>
        )}
      </div>
    </section>
  );
}

export default TelegramCard;
