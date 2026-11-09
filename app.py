import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import streamlit as st

# Configuração inicial da Página como Centralizada (para a tela de login)
st.set_page_config(
    page_title="Envio de Documentos em Massa", page_icon="📧", layout="wide"
)

# Função de Autenticação baseada no Secrets
def verificar_senha():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.subheader("🔐 Acesso Restrito - Login")
        senha_digitada = st.text_input(
            "Digite a senha de acesso ao sistema:", type="password"
        )

        if st.button("Entrar"):
            senha_correta = st.secrets.get("auth", {}).get(
                "senha_sistema", "123456"
            )
            if senha_digitada == senha_correta:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
        return False
    return True


# Verifica o login antes de renderizar o app
if not verificar_senha():
    st.stop()

# --- APLICAÇÃO PRINCIPAL ---
st.title("📧 Envio Automatizado de Documentos por E-mail")
st.write(
    "Selecione os destinatários, anexe os documentos individuais e faça o"
    " disparo em massa."
)

if "df_destinatarios" not in st.session_state:
    destinatarios_config = st.secrets.get("destinatarios_simples", {})

    if destinatarios_config:
        dados_iniciais = [
            {
                "Enviar": False,
                "Nome": nome,
                "Email": email,
                "Arquivo_Obj": None,
                "Nome_Arquivo": "",
            }
            for nome, email in destinatarios_config.items()
        ]
        st.session_state["df_destinatarios"] = pd.DataFrame(dados_iniciais)
    else:
        st.session_state["df_destinatarios"] = pd.DataFrame(
            columns=["Enviar", "Nome", "Email", "Arquivo_Obj", "Nome_Arquivo"]
        )

with st.sidebar:
    st.header("⚙️ Configurações & Ações")
    if st.button("🚪 Sair do Sistema"):
        st.session_state["autenticado"] = False
        st.rerun()

# Seção para adicionar destinatário manualmente se a tabela estiver vazia
st.subheader("👥 Gerenciar Destinatários")

col_add1, col_add2, col_add3 = st.columns([2, 2, 1], vertical_alignment="bottom")
with col_add1:
    novo_nome = st.text_input("Nome do Destinatário", key="input_nome")
with col_add2:
    novo_email = st.text_input("E-mail do Destinatário", key="input_email")
with col_add3:
    if st.button("Adicionar"):
        if novo_nome and novo_email:
            novo_registro = pd.DataFrame(
                [{
                    "Enviar": False,
                    "Nome": novo_nome,
                    "Email": novo_email,
                    "Arquivo_Obj": None,
                    "Nome_Arquivo": "",
                }]
            )
            st.session_state["df_destinatarios"] = pd.concat(
                [st.session_state["df_destinatarios"], novo_registro],
                ignore_index=True,
            )
            st.rerun()
        else:
            st.warning("Preencha nome e e-mail.")

# Exibição e Edição Interativa dos Destinatários com Checkbox e Upload por Linha
if not st.session_state["df_destinatarios"].empty:
    st.markdown("---")
    st.write(
        "### Selecione os destinatários e anexe os arquivos correspondentes:"
    )

    # Iterando sobre as linhas para criar uma interface customizada por usuário
    df_atual = st.session_state["df_destinatarios"]

    novas_linhas = []
    for index, row in df_atual.iterrows():
        # Reduzimos para 3 colunas, colocando a checkbox e o nome juntos na primeira
        col1, col2, col3 = st.columns([3, 3, 4], vertical_alignment="center")

        with col1:
            # Criamos duas sub-coluninhas internas para aproximar ao máximo a checkbox do nome
            sub_c1, sub_c2 = st.columns([0.2, 2.8], vertical_alignment="center")
            with sub_c1:
                sel = st.checkbox("", value=row["Enviar"], key=f"chk_{index}", label_visibility="collapsed")
            with sub_c2:
                st.markdown(f"**{row['Nome']}**")

        with col2:
            st.text(row["Email"])
            
        with col3:
            # Upload de arquivo individual
            uploaded_file = st.file_uploader(
                f"Anexo para {row['Nome']}",
                key=f"file_{index}",
                label_visibility="collapsed",
            )

            if uploaded_file is not None:
                nome_arq = uploaded_file.name
                bytes_arq = uploaded_file.getvalue()
            else:
                nome_arq = row["Nome_Arquivo"]
                bytes_arq = row["Arquivo_Obj"]

            if nome_arq:
                st.caption(f"📎 Vinculado: `{nome_arq}`")

        novas_linhas.append({
            "Enviar": sel,
            "Nome": row["Nome"],
            "Email": row["Email"],
            "Arquivo_Obj": bytes_arq,
            "Nome_Arquivo": nome_arq,
        })

    st.session_state["df_destinatarios"] = pd.DataFrame(novas_linhas)

    st.markdown("---")
    st.subheader("✉️ Configuração da Mensagem")

    assunto = st.text_input(
        "Assunto do E-mail",
        value="HOLERITE",
    )
    mensagem_corpo = st.text_area(
        "Corpo do E-mail",
        value=(
            "Segue Holerite em anexo.\n\nAtenciosamente,\nEliseu"
            " Mauro"
        ),
        height=150,
    )

    if st.button("🚀 Iniciar Envio em Massa", type="primary"):
        destinatarios_selecionados = st.session_state["df_destinatarios"][
            st.session_state["df_destinatarios"]["Enviar"] == True
        ]

        if destinatarios_selecionados.empty:
            st.warning("Nenhum destinatário foi selecionado para o envio.")
        else:
            # Carregar credenciais do secrets
            try:
                smtp_servidor = st.secrets["smtp"]["servidor"]
                smtp_porta = int(st.secrets["smtp"]["porta"])
                email_remetente = st.secrets["smtp"]["email_remetente"]
                senha_app = st.secrets["smtp"]["senha_app"]
            except Exception as e:
                st.error(
                    f"Erro ao carregar credenciais SMTP no arquivo secrets: {e}"
                )
                st.stop()

            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(destinatarios_selecionados)

            sucessos = 0
            erros = 0

            try:
                status_text.text("Conectando ao servidor SMTP...")
                server = smtplib.SMTP(smtp_servidor, smtp_porta)
                server.starttls()
                server.login(email_remetente, senha_app)

                for i, (_, row) in enumerate(destinatarios_selecionados.iterrows()):
                    status_text.text(
                        f"Enviando para {row['Nome']} ({row['Email']})..."
                    )

                    try:
                        msg = MIMEMultipart()
                        msg["From"] = email_remetente
                        msg["To"] = row["Email"]
                        msg["Subject"] = assunto

                        # Corpo do email personalizados com o nome
                        corpo_personalizado = f"Olá {row['Nome']},\n\n{mensagem_corpo}"
                        msg.attach(MIMEText(corpo_personalizado, "plain"))

                        # Anexo
                        if row["Arquivo_Obj"] is not None and row["Nome_Arquivo"]:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(row["Arquivo_Obj"])
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename= {row['Nome_Arquivo']}",
                            )
                            msg.attach(part)

                        server.sendmail(email_remetente, row["Email"], msg.as_string())
                        sucessos += 1
                    except Exception as ex:
                        erros += 1
                        st.error(f"Erro ao enviar para {row['Email']}: {ex}")

                    progress_bar.progress((i + 1) / total)

                server.quit()
                status_text.text("Envio concluído!")
                st.success(
                    f"Processo finalizado! E-mails enviados com sucesso: {sucessos} |"
                    f" Falhas: {erros}"
                )

            except Exception as e:
                st.error(f"Erro de conexão com o servidor SMTP: {e}")
else:
    st.info(
        "Nenhum destinatário cadastrado. Adicione manualmente acima."
    )
