# Especificação e Análise Estética de Referência
> **Origem:** Repositório `git@github.com:Edson-Teixeira/financeiro.git`  
> **Foco:** Hub Central de Módulos & Módulo / Aba Financeiro  
> **Destino:** Base de Design System para o `projeto_atlas_sistema`

---

## 1. Visão Geral e Filosofia Visual

A interface do sistema analisado adota uma estética **moderna, limpa, "dark-first" e orientada a dados financeiros**. Sua identidade visual remete a produtos SaaS contemporâneos (como Stripe, Linear e Raycast), priorizando:

1. **Clareza Numérica:** Destaque tipográfico para valores monetários com pesos fortes (`font-weight: 700` a `800`) e codificação por cores semânticas imediatas.
2. **Superfícies em Camadas (Layered Elevation):** Uso de até 3 níveis de profundidade de fundo (`bg-app`, `bg-surface`, `bg-surface-elevated`) com bordas sutis de contraste em vez de sombras pesadas e invasivas.
3. **Microinterações Fluidas:** Elevações suaves em cards (`translateY(-3px)` a `translateY(-6px)`), iluminação perimetral ao hover e botões com transição de opacidade/sombra.
4. **Bimodalidade Nativa:** Suporte total a **Dark Mode** (padrão principal) e **Light Mode**, com transição limpa orientada por variáveis CSS e persistência via `localStorage`.

---

## 2. Design Tokens e Fundações Visuais

### 2.1 Tipografia
* **Família Primária:** `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
* **Pesos Utilizados:**
  * `400` (Regular): Textos descritivos e observações secundárias.
  * `500` (Medium): Rótulos de categorias, itens de menu e metadados.
  * `600` (Semi-Bold): Títulos de seções intermediárias, botões e labels de formulário.
  * `700` (Bold): Títulos de cards, valores métricos e saldos.
  * `800` (Extra-Bold): Títulos principais de páginas (H1/H2), chamadas no Hub e números de faturas.

### 2.2 Paleta de Cores e Temas

#### Modo Escuro (Dark Mode - Padrão)
| Token CSS | Hexadecimal | Finalidade |
| :--- | :--- | :--- |
| `--bg-app` | `#0b0f17` | Fundo geral da aplicação (preto azulado profundo) |
| `--bg-surface` | `#111827` | Fundo de cards, sidebar, topbar e modais |
| `--bg-surface-elevated` | `#1a2234` | Fundo de itens internos, tabelas hover, badges neutros |
| `--bg-input` | `#151d2d` | Fundo de campos de formulário e inputs |
| `--border-color` | `#242f44` | Linha divisória e borda padrão de cartões |
| `--border-hover` | `#374765` | Borda em estado de foco ou hover |
| `--text-primary` | `#f8fafc` | Texto principal, cabeçalhos e números de alto contraste |
| `--text-secondary` | `#94a3b8` | Subtítulos, rótulos e textos explicativos |
| `--text-muted` | `#64748b` | Informações secundárias, timestamps e datas |

#### Modo Claro (Light Mode)
| Token CSS | Hexadecimal | Finalidade |
| :--- | :--- | :--- |
| `--bg-app` | `#f8fafc` | Fundo geral |
| `--bg-surface` | `#ffffff` | Fundo dos cards e containers |
| `--bg-surface-elevated` | `#f1f5f9` | Elementos elevados e fundos de destaque |
| `--border-color` | `#e2e8f0` | Linhas de divisão claras |
| `--text-primary` | `#0f172a` | Texto de alto contraste |
| `--text-secondary` | `#475569` | Texto secundário |

#### Cores Semânticas de Ação e Status
Cada cor semântica possui seu par com fundo translúcido (opacidade ~12-15%), gerando badges e caixas de ícones modernos:

| Semântica | Cor Sólida | Fundo Translúcido | Aplicação |
| :--- | :--- | :--- | :--- |
| **Primary (Índigo/Roxo)** | `#4f46e5` / `#7c3aed` | `rgba(79, 70, 229, 0.15)` | Botões de ação, itens ativos de menu, branding |
| **Success (Verde)** | `#10b981` | `rgba(16, 185, 129, 0.12)` | Receitas, status "Efetivado", saldo positivo |
| **Danger (Vermelho)** | `#ef4444` | `rgba(239, 68, 68, 0.12)` | Despesas, exclusões, saldo negativo, alertas |
| **Warning (Âmbar/Laranja)** | `#f59e0b` | `rgba(245, 158, 11, 0.12)` | Cartão de crédito, faturas abertas, pendências |
| **Info (Azul Sky)** | `#0ea5e9` | `rgba(14, 165, 233, 0.12)` | Saldo atual de conta, transferências, módulos auxiliares |
| **Purple (Violeta)** | `#8b5cf6` | `rgba(139, 92, 246, 0.12)` | Saldo previsto e projeções futuras |

### 2.3 Raios de Borda (Border Radius)
* `--radius-sm`: `8px` (inputs menores, tags internas)
* `--radius-md`: `12px` (botões padrão, inputs, itens de lista)
* `--radius-lg`: `16px` (cards de métricas, containers de conteúdo)
* `--radius-xl`: `20px` (cards do Hub de módulos e formulários principais)
* `--radius-full`: `9999px` (badges pílula, botões circulares, seletor de ciclos)

### 2.4 Sombras e Efeitos
* **Sombra Suave:** `0 1px 2px 0 rgba(0, 0, 0, 0.25)`
* **Sombra de Card (Elevação):** `0 4px 6px -1px rgba(0, 0, 0, 0.3)`
* **Glow Colorido Primário:** `0 4px 12px rgba(99, 102, 241, 0.35)` em botões e ícones principais.
* **Transição Padrão:** `all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`

---

## 3. Anatomia Estética do Hub (Central de Módulos)

O Hub é uma tela de entrada dedicada, focada em guiar o usuário na escolha do módulo de trabalho sem poluição visual.

```
+--------------------------------------------------------------------------+
|  [Logo] Sistema Integrado (Central de Módulos)             [Botão Tema]  |
+--------------------------------------------------------------------------+
|                                                                          |
|                            [ Hub Central ]                               |
|                  O que você deseja gerenciar hoje?                       |
|           Selecione um dos módulos abaixo para acessar seus...           |
|                                                                          |
|   +--------------------+  +--------------------+  +------------------+   |
|   | [Icon Gradiente]   |  | [Icon Gradiente]   |  | [Icon Gradiente] |   |
|   | Controle Financeiro|  | Gestão Veículos    |  | Investimentos    |   |
|   | Gestão de receitas,|  | Abastecimentos...  |  | Carteira B3...   |   |
|   | [Tag] [Tag] [Tag]  |  | [Tag] [Tag] [Tag]  |  | [Tag] [Tag]      |   |
|   |                    |  |                    |  |                  |   |
|   | [ Acessar Modulo ] |  | [ Acessar Modulo ] |  | [ Acessar Modulo]|   |
|   +--------------------+  +--------------------+  +------------------+   |
+--------------------------------------------------------------------------+
```

### 3.1 Destaques Visuais do Hub
1. **Fundo com Gradiente Radial Superior:**
   * Utiliza um leve feixe de luz roxo no topo:  
     `background: radial-gradient(circle at 50% 10%, rgba(79, 70, 229, 0.12) 0%, transparent 60%), var(--bg-app);`
   * Cria uma atmosfera de profundidade moderna sem tirar o contraste dos cartões.
2. **Hero Header Central:**
   * Badge pílula de apresentação: `Hub Central`.
   * Título imponente: `font-size: 34px`, `font-weight: 800`, `letter-spacing: -1px`.
   * Texto de apoio em tom `--text-secondary`, largura máxima de 680px para conforto de leitura.
3. **Grid de Módulos (`.modules-grid`):**
   * Grid com `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` e espaçamento de `24px`.
   * Limite máximo central de 1200px.
4. **Cards de Módulos (`.module-card`):**
   * **Container:** Fundo `--bg-surface`, borda de 1px com `--border-color`, raio de `20px` (`radius-xl`) e padding generoso de `32px 28px`.
   * **Efeito Hover:** Flutua `-6px` no eixo Y (`transform: translateY(-6px)`), acende a borda com `--primary` e projeta sombra suave colorida: `box-shadow: 0 16px 32px -8px rgba(79, 70, 229, 0.2)`.
   * **Ícone em Caixa Gradiente (60x60px):**
     * Cantos com `16px` de raio.
     * Ícones brancos com traço espesso (`stroke-width: 2.2`).
     * Gradiente diagonal a 135º para o módulo financeiro: `linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)` com sombra de `rgba(79, 70, 229, 0.35)`.
   * **Tags em Pílula (`.module-tag`):**
     * Indicam os recursos principais de cada módulo (ex: `5 Cards Dashboard`, `Cartões de Crédito`, `Ciclos Mensais`).
     * Fundo sutilmente elevado (`--bg-surface-elevated`), texto de tamanho `11px`, `font-weight: 600`.
   * **Botão Inferior Full-Width (`.module-btn`):**
     * Fixado na base do card, com ícone de seta (`→`) animado e texto claro de ação (`Acessar Financeiro`).

---

## 4. Anatomia Estética da Aba Financeiro (Módulo Financeiro)

O módulo financeiro é construído com foco em **densidade de informação inteligente**, controle por ciclos temporais e visão rápida de liquidez.

### 4.1 Estrutura de Layout Base
* **Sidebar Esquerda (260px):**
  * Ícone e nome do sistema com indicador dinâmico do módulo em uso.
  * **Botão Rápido de Retorno:** Botão no topo da sidebar `Trocar de Módulo →` permitindo alternar de volta ao Hub com apenas um clique.
  * Título de seção em minúsculo/caixa-alta discreta: `MENU FINANCEIRO` (`11px`, `letter-spacing: 0.8px`).
  * Links com ícones vetorizados, hover com deslocamento horizontal de `3px`, e link ativo com destaque à esquerda (`border-left: 3px solid var(--primary)` e fundo lilás sutil).
* **Topbar Superior (72px Sticky):**
  * **Seletor de Ciclos Mensais (Pill Component):** Barra no formato de pílula arredondada (`radius-full`) contendo botões circulares `<` e `>`, e o rótulo central do mês (ex: `Outubro / 2026`).
  * Ações à direita: Botão para retorno aos módulos e botão de troca de tema (lua/sol).
* **Área de Conteúdo Principal:** Limite máximo de `1400px` com `padding: 32px`.

---

### 4.2 Os 5 Cards Métricos de Topo (`.metrics-5-grid`)

O elemento mais característico da tela financeira é a fileira com 5 métricas essenciais dispostas lado a lado:

```
+---------------+ +---------------+ +---------------+ +---------------+ +---------------+
| RECEITAS  [+] | | DESPESAS  [-] | | SALDO ATUAL $ | | PREVISTO  (o) | | CARTÃO      [=]|
| R$ 8.450,00   | | R$ 3.210,00   | | R$ 5.240,00   | | R$ 6.100,00   | | R$ 1.890,00   |
| [Recebido]    | | [Pago]        | | [Efetivado]   | | [Projeção]    | | [Faturas]     |
| Previsto: ... | | Previsto: ... | | Realizado mês | | Final ciclo   | | Pagas: ...    |
+---------------+ +---------------+ +---------------+ +---------------+ +---------------+
```

1. **Card 1 - Receitas:**
   * Ícone: Caixa verde com seta ascendente.
   * Valor: `font-size: 22px`, cor `--success` (`#10b981`).
   * Subinfo: Badge verde `Recebido` + Texto `Previsto: R$ X`.
2. **Card 2 - Despesas:**
   * Ícone: Caixa vermelha com seta descendente.
   * Valor: `font-size: 22px`, cor `--danger` (`#ef4444`).
   * Subinfo: Badge vermelho `Pago` + Texto `Previsto: R$ X`.
3. **Card 3 - Saldo Atual (Efetivado):**
   * Ícone: Caixa azul sky com carteira.
   * Valor: Cor `--info` (`#0ea5e9`) se positivo, `--danger` se negativo.
   * Subinfo: Badge azul `Efetivado` + Texto `Realizado no mês`.
4. **Card 4 - Saldo Previsto (Projeção do Ciclo):**
   * Ícone: Caixa violeta com bússola.
   * Valor: Cor `--purple` (`#8b5cf6`) se positivo, `--danger` se negativo.
   * Subinfo: Badge neutro `Projeção` + Texto `Final do ciclo`.
5. **Card 5 - Despesa de Cartão de Crédito:**
   * Ícone: Caixa âmbar com cartão.
   * Valor: Cor `--warning` (`#f59e0b`).
   * Subinfo: Badge âmbar `Faturas` + Texto `Pagas: R$ X`.

---

### 4.3 Grid Central: Gráfico de Categorias e Saldos Bancários

Disposto em proporção `2fr 1fr`:

1. **Coluna Esquerda (Distribuição de Despesas):**
   * Gráfico de Rosca (Donut) via Chart.js com centro amplo (`cutout: 72%`).
   * Pareado lado a lado com lista de barras de progresso:
     * Bolinha colorida da categoria (`10px`).
     * Nome da categoria e valor absoluto com porcentagem.
     * Barra de fundo cinza escuro com trilho (`.progress-track`) e barra de preenchimento suave (`.progress-fill`) com a cor exata da categoria.
2. **Coluna Direita (Saldos das Contas):**
   * Lista compacta de contas cadastradas.
   * Avatar quadrado de 36x36px com as 2 primeiras letras do banco/conta e cor própria da instituição.
   * Badges contextuais (`Ciclo` para conta corrente, `Acumulado` para investimento).
   * Saldo formatado em negrito à direita.

---

### 4.4 Tabela de Últimas Movimentações
* Cabeçalhos em caixa alta reduzida (`11px`), cor `--text-muted`, tracking `0.6px`.
* Linhas com hover suave para `--bg-surface-elevated` e bordas inferiores finas.
* Indicador de categoria com ponto colorido (`8px` border-radius 50%).
* **Toggle de Status com 1 Clique:**
  * O badge de status (`Pendente` cinza / `Efetivado` verde) é um botão formulário direto, permitindo alterar o estado do lançamento sem abrir modais.
* Coluna de valor alinhada à direita, com sinal explícito (`+ R$ ...` ou `- R$ ...`).

---

### 4.5 Visão de Transações em 3 Colunas (Fluxo Financeiro)
Na página dedicada de transações (`transactions.html`):
* **Barra de Filtros:** Contém selects de categoria, status, campo de busca com ícone de lupa interno e botão de limpeza rápida.
* **Layout em 3 Colunas (`.trans-columns-grid`):**
  1. **Coluna 1 (Entradas):** Cabeçalho verde com contagem em badge e total somado.
  2. **Coluna 2 (Saídas):** Cabeçalho vermelho com contagem e total.
  3. **Coluna 3 (Transferências):** Cabeçalho azul com contagem e total.
* **Cards de Itens de Transação (`.trans-item`):**
  * Cada lançamento é um card próprio elevado, com descrição em destaque, conta associada, badge fixo de recorrência e ações discretas de edição/exclusão.

---

### 4.6 Cards Estilo Cartão de Crédito Físico (`cards.html`)
* Card dividido em duas metades:
  1. **Metade Superior (Estilo Cartão Físico):** Gradiente diagonal da cor configurada do cartão para o escuro (`linear-gradient(135deg, {{ card.color }} 0%, #0f172a 100%)`). Traz o nome do cartão, bandeira em badge translúcido, total da fatura em tamanho `24px` e datas de fechamento e vencimento.
  2. **Metade Inferior:** Métricas detalhadas (status da fatura, limite total, limite disponível em verde e conta vinculada de débito).

---

### 4.7 Padrão de Formulários (`form-card`)
* Container centralizado (`max-width: 640px`) com cantos de `20px` de raio.
* Campos agrupados em linhas duplas (`.form-row` com `grid-template-columns: 1fr 1fr`).
* Inputs com fundo `--bg-input`, borda suave e foco com anel iluminado de 3px (`box-shadow: 0 0 0 3px var(--primary-light)`).

---

## 5. Resumo das Regras Estéticas para o Novo Projeto (`projeto_atlas_sistema`)

Para manter a consistência com essa referência no novo projeto, recomenda-se adotar:

| Elemento | Regra Recomendada |
| :--- | :--- |
| **Fonte** | `Plus Jakarta Sans` para toda a aplicação. |
| **Fundo Geral** | Fundo ultra-escuro `#0b0f17` com cards em `#111827` e relevos em `#1a2234`. |
| **Contraste de Bordas** | Bordas finas de 1px `#242f44` em vez de separadores brancos ou sombras opacas. |
| **Cores Semânticas** | Verde `#10b981` (entradas/lucro), Vermelho `#ef4444` (saídas/prejuízo), Âmbar `#f59e0b` (cartões/atenção), Roxo `#8b5cf6` (projeções). |
| **Raios de Curvatura** | Padrão `12px` para botões/inputs, `16px` para cards de dashboard e `20px` para cards do Hub e modais. |
| **Badges de Status** | Sempre no formato de pílula (`radius-full`) com fundo translúcido (12% opacidade) e texto com a cor sólida. |
| **Navegação** | Sidebar retrátil no mobile, seletor de ciclos temporais no topo e atalho persistente para troca de módulos. |
| **Interações** | Efeito de elevação leve ao passar o mouse (`translateY(-2px)` a `-4px`) e botões primários com leve glow. |

---
*Documento gerado automaticamente para servir como diretriz visual do `projeto_atlas_sistema`.*
